#!/usr/bin/env python3
"""Stream wrapped command output to a private log and a bounded display."""

import codecs
from collections import deque
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
from importlib.abc import Loader
from importlib.machinery import ModuleSpec
from pathlib import Path
from typing import BinaryIO, cast

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mtk_jobs import Tracker, prepare_state


runner_spec = cast(ModuleSpec, importlib.util.spec_from_file_location("mtk_runner_sizes", Path(__file__).with_name("mtk-runner.py")))
runner_sizes = importlib.util.module_from_spec(runner_spec)
cast(Loader, runner_spec.loader).exec_module(runner_sizes)
parse_bytes = runner_sizes.parse_bytes
MARKER = b"[truncated by mtk]\n"
RESOURCE_VALUE_FLAGS = {"--time-limit", "--memory-limit", "--mem-limit", "--cpu-limit"}
DISPLAY_VALUE_FLAGS = {"--max-lines", "--max-bytes"}
SHORT_RESOURCE_FLAGS = {
    "--time": "--time-limit",
    "--memory": "--memory-limit",
    "--cpu": "--cpu-limit",
    "--root-only": "--exclude-children",
}


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
        return 80, 32768, True
    except (OSError, ValueError) as exc:
        raise ValueError(f"config {path}: {exc}") from exc
    try:
        if not isinstance(config, dict):
            raise ValueError("expected JSON object")
        unknown = config.keys() - {"max_lines", "max_bytes", "truncate"}
        if unknown:
            raise ValueError(f"unknown settings: {', '.join(sorted(unknown))}")
        lines = config.get("max_lines", 80)
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
        separator = len(args) - 1 - args[::-1].index("--")
        suffix = args[separator + 1:]
        value_flags = RESOURCE_VALUE_FLAGS | DISPLAY_VALUE_FLAGS | {"--singleton-name"}
        boolean_flags = {"--exclude-children", "--no-truncate", "--singleton", "--singleton-wait"}
        explicit_flags = DISPLAY_VALUE_FLAGS | {"--no-truncate", "--singleton", "--singleton-wait", "--singleton-name"} | SHORT_RESOURCE_FLAGS.keys()
        if suffix and suffix[0].partition("=")[0] in explicit_flags:
            normalized = []
            index = 0
            while index < len(suffix):
                flag, equal, value = suffix[index].partition("=")
                option = flag
                flag = SHORT_RESOURCE_FLAGS.get(flag, flag)
                if flag in value_flags:
                    if not equal:
                        index += 1
                        if index >= len(suffix):
                            raise ValueError(f"{option} requires a value")
                        value = suffix[index]
                    if not value or value.startswith("--"):
                        raise ValueError(f"{option} requires a value")
                    normalized.extend((flag, value))
                elif flag in boolean_flags and (not equal or flag in {"--singleton", "--singleton-wait"}):
                    normalized.append(f"{flag}={value}" if equal else flag)
                else:
                    raise ValueError(f"unexpected MTK option: {suffix[index]}")
                index += 1
            return args[:separator], normalized
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
    def __init__(self, max_lines, max_bytes, truncate):
        self.head_lines = (max_lines + 1) // 2
        self.tail_lines = max_lines // 2
        self.max_bytes = max_bytes
        self.truncate = truncate
        self.lines = self.size = self.chars = self.words = 0
        self.in_word = self.exhausted = False
        self.clipped = False
        self.ends_newline = True
        self.last_stream = sys.stdout.buffer
        self.decoders = {}
        self.sinks = {}
        self.tail = deque(maxlen=self.tail_lines)
        self.pending = []
        self.pending_chars = self.pending_bytes = 0
        self.pending_clipped = False

    def write(self, stream, data, final=False):
        if not self.truncate:
            self.emit(stream, data)
            return
        if self.exhausted:
            return
        decoder = self.decoders.setdefault(stream, codecs.getincrementaldecoder("utf-8")("surrogateescape"))
        text = decoder.decode(data, final=final)
        parts = text.split("\n")
        for index, part in enumerate(parts):
            newline = index < len(parts) - 1
            fragment = part + ("\n" if newline else "")
            if not fragment:
                continue
            if self.lines < self.head_lines:
                self.bounded_emit(stream, fragment)
            else:
                room = 8000 - self.pending_chars
                retained_chars = []
                retained_bytes = 0
                for char in fragment[:room]:
                    size = len(char.encode("utf-8", "surrogateescape"))
                    if self.pending_bytes + retained_bytes + size > self.max_bytes:
                        break
                    retained_chars.append(char)
                    retained_bytes += size
                retained = "".join(retained_chars)
                self.pending_clipped |= len(retained) < len(fragment)
                if retained:
                    if self.pending and self.pending[-1][0] is stream:
                        self.pending[-1] = (stream, self.pending[-1][1] + retained)
                    else:
                        self.pending.append((stream, retained))
                    self.pending_chars += len(retained)
                    self.pending_bytes += retained_bytes
            if newline:
                if self.lines >= self.head_lines:
                    self.close_line()
                self.lines += 1
            if self.exhausted:
                break

    def close_line(self):
        if len(self.tail) == self.tail_lines:
            self.clipped = True
        self.tail.append((self.pending, self.pending_clipped))
        self.pending = []
        self.pending_chars = self.pending_bytes = 0
        self.pending_clipped = False

    def bounded_emit(self, stream, text):
        if self.exhausted:
            return
        prefix = bytearray()
        for char in text:
            encoded = char.encode("utf-8", "surrogateescape")
            new_word = not char.isspace() and not self.in_word
            if self.chars >= 8000 or self.size + len(encoded) > self.max_bytes or (new_word and self.words >= 1500):
                self.clipped = self.exhausted = True
                break
            prefix.extend(encoded)
            self.size += len(encoded)
            self.chars += 1
            self.words += new_word
            self.in_word = not char.isspace()
        self.emit(stream, prefix)

    def finish(self):
        if self.truncate:
            if self.pending or self.pending_clipped:
                self.close_line()
            for segments, clipped in self.tail:
                self.clipped |= clipped
                for stream, text in segments:
                    self.bounded_emit(stream, text)
            if self.clipped:
                self.emit(self.last_stream, (b"" if self.ends_newline else b"\n") + MARKER)

    def emit(self, stream, data):
        if data:
            sink = self.sinks.get(stream, stream)
            try:
                sink.write(data)
                sink.flush()
            except BrokenPipeError:
                # Keep draining and logging even when a downstream pipe closes.
                self.sinks[stream] = open(os.devnull, "wb", buffering=0)
            self.last_stream = stream
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
    termination_signal = 0
    forced_status = None
    status = None
    display = Display(max_lines, max_bytes, truncate)
    if terminal:
        env["MTK_OUTPUT_TTY"] = "1"
        pid, master = pty.fork()
        if pid == 0:
            os.execvpe(command[0], command, env)
        selector.register(master, selectors.EVENT_READ, sys.stdout.buffer)
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
        selector.register(cast(BinaryIO, child.stdout), selectors.EVENT_READ, sys.stdout.buffer)
        selector.register(cast(BinaryIO, child.stderr), selectors.EVENT_READ, sys.stderr.buffer)

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
                        os.write(cast(int, master), data)
                    else:
                        selector.unregister(key.fileobj)
                elif data:
                    log.write(data)
                    display.write(key.data, data)
                else:
                    display.write(key.data, b"", final=True)
                    selector.unregister(key.fileobj)
        display.finish()
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
                cast(BinaryIO, child.stdout).close()
                cast(BinaryIO, child.stderr).close()


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
