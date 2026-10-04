import errno
import fcntl
import os
from pathlib import Path
import pty
import re
import select
import signal
import subprocess
import struct
import sys
import time
import termios
import unittest


ROOT = Path(__file__).resolve().parents[1]
MTK = str(ROOT / "bin/mtk")


class OutputTests(unittest.TestCase):
    def test_governed_terminal_has_controlling_tty_and_resize(self):
        pid, fd = pty.fork()
        if pid == 0:
            os.execv(MTK, [MTK, "--time-limit", "4s", "proxy", sys.executable, "-c",
                "import signal,time; f=open('/dev/tty'); signal.signal(signal.SIGWINCH,lambda *_: print('RESIZED',flush=True)); print('READY',flush=True); time.sleep(1)"])
        output = bytearray()
        resized = False
        try:
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                if select.select([fd], [], [], 0.2)[0]:
                    try:
                        chunk = os.read(fd, 65536)
                    except OSError as exc:
                        if exc.errno == errno.EIO:
                            break
                        raise
                    if not chunk:
                        break
                    output.extend(chunk)
                    if b"READY" in output.splitlines() and not resized:
                        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 42, 120, 0, 0))
                        resized = True
            self.assertIn(b"READY", output.splitlines())
            self.assertIn(b"RESIZED", output.splitlines())
        finally:
            os.close(fd)
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.waitpid(pid, 0)
            for match in re.findall(rb"(?m)^(/tmp/mtk-[^\r\n]+\.log)\r?$", output):
                Path(os.fsdecode(match)).unlink(missing_ok=True)

    def test_help_exposes_output_and_governor_flags(self):
        result = subprocess.run([MTK, "--help"], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        for flag in (b"--max-lines", b"--max-bytes", b"--no-truncate", b"--exclude-children"):
            self.assertIn(flag, result.stdout)

    def run_mtk(self, script, flags=()):
        result = subprocess.run(
            [MTK, *flags, "proxy", sys.executable, "-c", script],
            capture_output=True, timeout=15,
        )
        match = re.search(rb"(?m)^(/tmp/mtk-[^\r\n]+\.log)\r?$", result.stderr)
        self.assertIsNotNone(match, result.stderr)
        path = Path(os.fsdecode(match[1]))
        self.addCleanup(path.unlink, missing_ok=True)
        return result, path.read_bytes()

    def test_short_output_log_has_only_command_bytes(self):
        result, log = self.run_mtk("import os; os.write(1,b'hello')")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"hello")
        self.assertEqual(log, b"hello")
        self.assertNotIn(b"[truncated by mtk]", result.stderr)

    def test_line_limit_has_marker_and_complete_log(self):
        result, log = self.run_mtk("print('one\\ntwo\\nthree')", ["--max-lines", "2"])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"one\ntwo\n[truncated by mtk]\n")
        self.assertEqual(log, b"one\ntwo\nthree\n")

    def test_byte_limit_preserves_utf8(self):
        result, log = self.run_mtk("print('ééé',end='')", ["--max-bytes", "5"])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.decode(), "éé\n[truncated by mtk]\n")
        self.assertEqual(log.decode(), "ééé")

    def test_no_truncate_still_logs(self):
        result, log = self.run_mtk("print('x'*70000,end='')", ["--no-truncate"])
        self.assertEqual(result.stdout, b"x" * 70000)
        self.assertEqual(log, result.stdout)

    def test_both_streams_drained_and_exit_preserved(self):
        result, log = self.run_mtk(
            "import os,sys; os.write(1,b'out\\n'); os.write(2,b'err\\n'); sys.exit(7)"
        )
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout, b"out\n")
        self.assertEqual(result.stderr.splitlines()[0], b"err")
        self.assertIn(log, (b"out\nerr\n", b"err\nout\n"))

    def test_large_output_has_default_limits_and_full_log(self):
        result, log = self.run_mtk("import os; os.write(1,b'x\\n'*200000)")
        self.assertEqual(result.stdout, b"x\n" * 200 + b"[truncated by mtk]\n")
        self.assertEqual(log, b"x\n" * 200000)

    def test_oversized_line_uses_byte_limit(self):
        result, log = self.run_mtk("print('x'*40000,end='')")
        self.assertEqual(result.stdout, b"x" * 32768 + b"\n[truncated by mtk]\n")
        self.assertEqual(log, b"x" * 40000)

    def test_governor_creates_only_one_log_footer(self):
        result, log = self.run_mtk("print('bounded')", ["--time-limit", "5s"])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(re.findall(rb"/tmp/mtk-[^\r\n]+\.log", result.stderr)), 1)
        self.assertEqual(log, b"bounded\n")

    def test_stderr_truncation_footer_is_last_and_log_is_private(self):
        result, log = self.run_mtk(
            "import os; os.write(2,b'one\\ntwo\\nthree')", ["--max-lines", "2"])
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stderr.startswith(b"one\ntwo\n[truncated by mtk]\n"))
        path = Path(os.fsdecode(result.stderr.splitlines()[-1]))
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(log, b"one\ntwo\nthree")

    def test_invalid_limits_are_rejected(self):
        for flag, value in (("--max-lines", "0"), ("--max-bytes", "-1")):
            result = subprocess.run([MTK, flag, value, "proxy", "echo", "must-not-run"],
                capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn(b"must-not-run", result.stdout)

    def test_exact_limit_does_not_claim_truncation(self):
        result, log = self.run_mtk("print('one\\ntwo')", ["--max-lines", "2"])
        self.assertEqual(result.stdout, b"one\ntwo\n")
        self.assertEqual(log, result.stdout)

    def test_terminal_child_keeps_tty_and_accepts_stdin(self):
        pid, fd = pty.fork()
        if pid == 0:
            os.execv(MTK, [MTK, "proxy", sys.executable, "-c",
                "import os; print('TTY',os.isatty(0),os.isatty(1),flush=True); print(input(),flush=True)"])
        self.addCleanup(os.close, fd)
        try:
            output = bytearray()
            sent = False
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                if select.select([fd], [], [], 0.2)[0]:
                    try:
                        chunk = os.read(fd, 65536)
                    except OSError as exc:
                        if exc.errno == errno.EIO:
                            break
                        raise
                    if not chunk:
                        break
                    output.extend(chunk)
                    if b"TTY True True" in output and not sent:
                        os.write(fd, b"echo-input\n")
                        sent = True
            self.assertIn(b"TTY True True", output)
            self.assertIn(b"echo-input", output)
            match = re.search(rb"(?m)^(/tmp/mtk-[^\r\n]+\.log)\r?$", output)
            self.assertIsNotNone(match, output)
            path = Path(os.fsdecode(match[1]))
            self.addCleanup(path.unlink, missing_ok=True)
            self.assertNotIn(b"[truncated by mtk]", path.read_bytes())
        finally:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.waitpid(pid, 0)


if __name__ == "__main__":
    unittest.main()
