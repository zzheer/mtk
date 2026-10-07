#!/usr/bin/env python3
"""Stream wrapped command output to a private log and a bounded display."""

import codecs
import errno
import fcntl
import json
import os
import pty
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time
import termios
import tty

import importlib.util
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mtk_jobs import Tracker, prepare_state


runner_spec = importlib.util.spec_from_file_location("mtk_runner_sizes", Path(__file__).with_name("mtk-runner.py"))
runner_sizes = importlib.util.module_from_spec(runner_spec)
runner_spec.loader.exec_module(runner_sizes)
parse_bytes = runner_sizes.parse_bytes
MARKER = b"[truncated by mtk]\n"
RESOURCE_VALUE_FLAGS = {"--time-limit", "--memory-limit", "--mem-limit", "--cpu-limit"}
DISPLAY_VALUE_FLAGS = {"--max-lines", "--max-bytes"}


class CaptureFailure(Exception):
    def __init__(self, error, status):
        super().__init__(str(error))
        self.status = status


def defaults():
    directory = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    path = Path(directory) / "mtk/config.json"
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError("expected a regular JSON file")
            with os.fdopen(fd, encoding="utf-8") as file:
                fd = -1
                contents = file.read(65537)
        finally:
            if fd >= 0:
                os.close(fd)
        if len(contents) > 65536:
            raise ValueError("file exceeds 64 Ki characters")
        config = json.loads(contents)
    except FileNotFoundError:
        return 200, 32768, True
    except (OSError, ValueError) as exc:
        raise ValueError(f"config {path}: {exc}") from exc
    try:
        if not isinstance(config, dict):
            raise ValueError("expected JSON object")
        unknown = config.keys() - {"max_lines", "max_bytes", "truncate"}
        if unknown:
            raise ValueError(f"unknown settings: {', '.join(sorted(unknown))}")
        lines = config.get("max_lines", 200)
        size = config.get("max_bytes", 32768)
        truncate = config.get("truncate", True)
        if type(lines) is not int or lines <= 0:
            raise ValueError("max_lines must be a positive integer")
        if type(size) not in (int, str):
            raise ValueError("max_bytes must be a positive integer or size string")
        size = parse_bytes(str(size))
        if size <= 0:
            raise ValueError("max_bytes must be positive")
        if type(truncate) is not bool:
            raise ValueError("truncate must be boolean")
        return lines, size, truncate
    except ValueError as exc:
        raise ValueError(f"config {path}: {exc}") from exc


def resource_suffix(args):
    if "--" in args[1:]:
        return args, []
    end = len(args)
    while end > 1:
        arg = args[end - 1]
        flag, equal, value = arg.partition("=")
        if arg in {"--exclude-children", "--no-truncate"}:
            end -= 1
        elif flag in RESOURCE_VALUE_FLAGS | DISPLAY_VALUE_FLAGS:
            if not equal or not value:
                raise ValueError(f"{flag} requires a value")
            end -= 1
        elif end > 2 and args[end - 2] in RESOURCE_VALUE_FLAGS | DISPLAY_VALUE_FLAGS:
            if not arg:
                raise ValueError(f"{args[end - 2]} requires a value")
            end -= 2
        else:
            break
    return args[:end], args[end:]


def options(argv):
    max_lines, max_bytes, truncate = defaults()
    resources, globals_, wrapped = [], [], []
    rest = list(argv[1:])
    value_flags = RESOURCE_VALUE_FLAGS | {"--singleton-name"}
    suffix = False
    while rest:
        arg = rest.pop(0)
        flag, equal, value = arg.partition("=")
        if flag in DISPLAY_VALUE_FLAGS:
            if not equal:
                if not rest:
                    raise ValueError(f"{flag} requires a value")
                value = rest.pop(0)
            if flag == "--max-lines":
                max_lines = int(value)
                if max_lines <= 0:
                    raise ValueError("--max-lines must be positive")
            else:
                max_bytes = parse_bytes(value)
                if max_bytes <= 0:
                    raise ValueError("--max-bytes must be positive")
        elif arg == "--no-truncate":
            truncate = False
        elif flag in value_flags:
            if not equal:
                if not rest:
                    raise ValueError(f"{flag} requires a value")
                value = rest.pop(0)
            if not value:
                raise ValueError(f"{flag} requires a value")
            resources.extend((flag, value))
        elif arg == "--exclude-children" or flag in {"--singleton", "--singleton-wait"}:
            resources.append(arg)
        elif not arg.startswith("-") or arg == "--":
            if suffix:
                raise ValueError(f"unexpected MTK option: {arg}")
            wrapped, rest = resource_suffix(rest if arg == "--" else [arg, *rest])
            if arg == "--":
                globals_.append(arg)
            suffix = True
        else:
            globals_.append(arg)
    command = [argv[0], *resources, *globals_, *wrapped]
    return command, max_lines, max_bytes, truncate


class Display:
    def __init__(self, stream, max_lines, max_bytes, truncate):
        self.stream = stream
        self.max_lines, self.max_bytes = max_lines, max_bytes
        self.truncate = truncate
        self.lines = self.size = 0
        self.clipped = False
        self.ends_newline = True
        self.decoder = codecs.getincrementaldecoder("utf-8")("surrogateescape")

    def write(self, data, final=False):
        if not self.truncate:
            self.emit(data)
            return
        text = self.decoder.decode(data, final=final)
        if self.clipped:
            return
        prefix = bytearray()
        for char in text:
            encoded = char.encode("utf-8", "surrogateescape")
            if self.lines >= self.max_lines or self.size + len(encoded) > self.max_bytes:
                self.emit(prefix)
                self.emit((b"" if self.ends_newline else b"\n") + MARKER)
                self.clipped = True
                return
            prefix.extend(encoded)
            self.size += len(encoded)
            self.lines += char == "\n"
        self.emit(prefix)

    def emit(self, data):
        if data:
            try:
                self.stream.write(data)
                self.stream.flush()
            except BrokenPipeError:
                # Keep draining and logging even when a downstream pipe closes.
                self.stream = open(os.devnull, "wb", buffering=0)
            self.ends_newline = data.endswith(b"\n")


def execute(command, log, max_lines, max_bytes, truncate):
    # Management commands are captured but never registered as workloads.
    index = 1
    while index < len(command) and command[index].startswith("-"):
        flag, equal, _ = command[index].partition("=")
        index += 2 if flag in RESOURCE_VALUE_FLAGS | {"--singleton-name"} and not equal else 1
    management = index < len(command) and command[index] in {"jobs", "stop"}
    if not management:
        prepare_state()
    terminal = all(os.isatty(fd) for fd in (0, 1, 2))
    env = {**os.environ, "MTK_OUTPUT_INTERNAL": "1"}
    env["MTK_JOB_CAPTURED"] = "1"
    env.pop("MTK_OUTPUT_TTY", None)
    selector = selectors.DefaultSelector()
    saved_terminal = None
    child = None
    master = None
    tracker = None
    tracking_failed = False
    pending_signal = None
    stop_deadline = None
    termination_signal = None
    forced_status = None
    status = None
    if terminal:
        env["MTK_OUTPUT_TTY"] = "1"
        pid, master = pty.fork()
        if pid == 0:
            os.execvpe(command[0], command, env)
        selector.register(master, selectors.EVENT_READ, Display(sys.stdout.buffer, max_lines, max_bytes, truncate))
        selector.register(0, selectors.EVENT_READ, None)
        saved_terminal = termios.tcgetattr(0)
        tty.setraw(0)

        def resize(sig=None, frame=None):
            try:
                size = fcntl.ioctl(0, termios.TIOCGWINSZ, b"\0" * 8)
                fcntl.ioctl(master, termios.TIOCSWINSZ, size)
            except OSError:
                pass

        resize()
        signal.signal(signal.SIGWINCH, resize)
    else:
        child = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        pid = child.pid
        selector.register(child.stdout, selectors.EVENT_READ, Display(sys.stdout.buffer, max_lines, max_bytes, truncate))
        selector.register(child.stderr, selectors.EVENT_READ, Display(sys.stderr.buffer, max_lines, max_bytes, truncate))

    def forward(sig, frame):
        nonlocal pending_signal
        pending_signal = sig

    def completed():
        nonlocal status
        if status is None:
            if child:
                status = child.poll()
            else:
                waited, code = os.waitpid(pid, os.WNOHANG)
                if waited:
                    status = os.waitstatus_to_exitcode(code)
        return status is not None

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, forward)
    try:
        if not management:
            tracker = Tracker(pid, command[1:], persist=False)
            tracker.persist = True
        while (any(key.data is not None for key in selector.get_map().values())
               or not completed() or stop_deadline is not None):
            if tracker:
                tracker.refresh()
            if pending_signal is not None:
                forwarded_signal = pending_signal
                if tracker:
                    tracker.signal(pending_signal)
                else:
                    try:
                        os.kill(pid, pending_signal)
                    except ProcessLookupError:
                        pass
                pending_signal = None
                if forwarded_signal != signal.SIGINT:
                    termination_signal = forwarded_signal
                    stop_deadline = time.monotonic() + 1
            if stop_deadline is not None and time.monotonic() >= stop_deadline:
                if not completed():
                    forced_status = 128 + termination_signal
                if tracker:
                    tracker.signal(signal.SIGKILL)
                stop_deadline = None
            for key, _ in selector.select(timeout=0.1):
                try:
                    data = os.read(key.fd, 65536)
                except OSError as exc:
                    if terminal and exc.errno == errno.EIO:
                        data = b""
                    else:
                        raise
                if key.data is None:
                    if data:
                        os.write(master, data)
                    else:
                        selector.unregister(key.fileobj)
                elif data:
                    log.write(data)
                    key.data.write(data)
                else:
                    key.data.write(b"", final=True)
                    selector.unregister(key.fileobj)
        return forced_status if forced_status is not None else status
    except BaseException as exc:
        tracking_failed = True
        if tracker:
            # Cleanup must not depend on the registry that may have failed.
            tracker.persist = False
            tracker.signal(signal.SIGKILL)
        elif not completed():
            try:
                # Initial discovery can fail after a governor creates a separate
                # worker group. Let that governor clean up before killing it.
                os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            # Allow the governor's initial snapshot and both cleanup snapshots
            # (each bounded to 3s), plus its 1s escalation grace.
            deadline = time.monotonic() + 10
            while not completed() and time.monotonic() < deadline:
                time.sleep(0.02)
            if not completed():
                try:
                    os.killpg(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        if not completed():
            if child:
                child.wait()
            else:
                os.waitpid(pid, 0)
        interrupted = pending_signal or termination_signal
        if interrupted in (signal.SIGTERM, signal.SIGHUP):
            raise CaptureFailure(exc, 128 + interrupted) from exc
        raise
    finally:
        try:
            if tracker and not tracking_failed:
                tracker.finish()
        finally:
            selector.close()
            if saved_terminal is not None:
                termios.tcsetattr(0, termios.TCSADRAIN, saved_terminal)
            if master is not None:
                os.close(master)
            if child:
                child.stdout.close()
                child.stderr.close()


def main():
    try:
        command, max_lines, max_bytes, truncate = options(sys.argv[1:])
    except (ValueError, IndexError) as exc:
        print(f"mtk: {exc}", file=sys.stderr)
        return 2
    path = None
    try:
        fd, path = tempfile.mkstemp(prefix="mtk-", suffix=".log", dir="/tmp")
        with os.fdopen(fd, "wb", buffering=0) as log:
            code = execute(command, log, max_lines, max_bytes, truncate)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, CaptureFailure) as exc:
        print(f"\nmtk: command capture failed: {exc}", file=sys.stderr)
        if path:
            print(f"mtk: incomplete log: {path}", file=sys.stderr)
        return exc.status if isinstance(exc, CaptureFailure) else 1
    # stderr gets its own line even if the command did not end in a newline.
    print(f"\n{path}", file=sys.stderr, flush=True)
    return code if code >= 0 else 128 - code


if __name__ == "__main__":
    sys.exit(main())
