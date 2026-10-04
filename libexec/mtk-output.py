#!/usr/bin/env python3
"""Stream wrapped command output to a private log and a bounded display."""

import codecs
import errno
import fcntl
import os
import pty
import selectors
import signal
import subprocess
import sys
import tempfile
import termios
import tty

import importlib.util
from pathlib import Path


runner_spec = importlib.util.spec_from_file_location("mtk_runner_sizes", Path(__file__).with_name("mtk-runner.py"))
runner_sizes = importlib.util.module_from_spec(runner_spec)
runner_spec.loader.exec_module(runner_sizes)
parse_bytes = runner_sizes.parse_bytes
MARKER = b"[truncated by mtk]\n"


def options(argv):
    max_lines, max_bytes, truncate = 200, 32768, True
    command = [argv[0]]
    rest = argv[1:]
    value_flags = {"--time-limit", "--memory-limit", "--mem-limit", "--cpu-limit", "--singleton-name"}
    while rest:
        arg = rest.pop(0)
        flag, equal, value = arg.partition("=")
        if flag in ("--max-lines", "--max-bytes"):
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
        else:
            command.append(arg)
            if arg in value_flags:
                if not rest:
                    raise ValueError(f"{arg} requires a value")
                command.append(rest.pop(0))
            elif not arg.startswith("-") or arg == "--":
                command.extend(rest)
                break
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
    terminal = all(os.isatty(fd) for fd in (0, 1, 2))
    env = {**os.environ, "MTK_OUTPUT_INTERNAL": "1"}
    env.pop("MTK_OUTPUT_TTY", None)
    selector = selectors.DefaultSelector()
    saved_terminal = None
    child = None
    master = None
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
        try:
            os.killpg(pid, sig)
        except ProcessLookupError:
            pass

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, forward)
    try:
        while any(key.data is not None for key in selector.get_map().values()):
            for key, _ in selector.select():
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
        return child.wait() if child else os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1])
    except BaseException:
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        if child:
            child.wait()
        else:
            os.waitpid(pid, 0)
        raise
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
    except OSError as exc:
        print(f"\nmtk: command capture failed: {exc}", file=sys.stderr)
        if path:
            print(f"mtk: incomplete log: {path}", file=sys.stderr)
        return 1
    # stderr gets its own line even if the command did not end in a newline.
    print(f"\n{path}", file=sys.stderr, flush=True)
    return code if code >= 0 else 128 - code


if __name__ == "__main__":
    sys.exit(main())
