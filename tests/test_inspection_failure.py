"""Real-process regressions for ps failure after successful MTK tracking.

Run against an unchanged source tree; all fixtures remain outside that tree.
"""
import importlib.util
import json
import errno
import fcntl
import pty
import termios
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('inspection_jobs', SOURCE / 'libexec/mtk_jobs.py')
jobs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jobs)


class InspectionFailureRegression(unittest.TestCase):
    def exercise(self, standalone=False, terminal=False, interrupted=False):
        with tempfile.TemporaryDirectory(prefix='inspection-fixture-') as temporary:
            fixture = Path(temporary)
            ready = fixture / 'ready'
            state = fixture / 'state'
            fakebin = fixture / 'bin'
            fakebin.mkdir()
            fake_ps = fakebin / 'ps'
            fake_ps.write_text(
                '#!' + sys.executable + '\n'
                'import glob, os, signal, sys\n'
                'if os.path.exists(os.environ["INSPECTION_READY"]) and '
                'glob.glob(os.environ["XDG_STATE_HOME"] + "/mtk/jobs/*.json"):\n'
                '    print("injected persistent ps snapshot failure", file=sys.stderr)\n'
                + ('    os.kill(os.getppid(), signal.SIGTERM)\n'
                   '    os.kill(os.getpid(), signal.SIGTERM)\n' if interrupted else '    sys.exit(73)\n')
                +
                'os.execv("/bin/ps", ["/bin/ps"] + sys.argv[1:])\n'
            )
            fake_ps.chmod(0o700)
            worker = [sys.executable, '-c',
                      'import os, pathlib, time; '
                      'pathlib.Path(os.environ["INSPECTION_READY"]).write_text(str(os.getpid())); '
                      'time.sleep(20)']
            command = ([sys.executable, str(SOURCE / 'libexec/mtk-runner.py'), '--']
                       if standalone else [str(SOURCE / 'bin/mtk')]) + worker
            env = {**os.environ, 'PATH': str(fakebin) + ':' + os.environ['PATH'],
                   'XDG_STATE_HOME': str(state), 'XDG_CONFIG_HOME': str(fixture / 'config'),
                   'INSPECTION_READY': str(ready), 'PYTHONDONTWRITEBYTECODE': '1'}
            for key in ('MTK_JOB_CAPTURED', 'MTK_OUTPUT_INTERNAL', 'MTK_OUTPUT_TTY'):
                env.pop(key, None)
            process = None
            known = {}
            master = slave = None
            captured = bytearray()
            try:
                if terminal:
                    master, slave = pty.openpty()
                    baseline = termios.tcgetattr(slave)
                    def control_terminal():
                        os.setsid()
                        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
                    process = subprocess.Popen(command, env=env, stdin=slave,
                        stdout=slave, stderr=slave, preexec_fn=control_terminal)
                    os.close(slave)
                    slave = None
                    os.set_blocking(master, False)
                else:
                    process = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL,
                                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                               start_new_session=True)
                def drain_terminal():
                    while True:
                        try:
                            data = os.read(master, 65536)
                        except OSError as exc:
                            if exc.errno in (errno.EAGAIN, errno.EIO):
                                return
                            raise
                        if not data:
                            return
                        captured.extend(data)
                deadline = time.monotonic() + 8
                while process.poll() is None and time.monotonic() < deadline:
                    if terminal:
                        drain_terminal()
                    time.sleep(0.02)
                self.assertIsNotNone(process.poll(), 'MTK did not exit after injected ps failure')
                self.assertEqual(process.returncode, 143 if interrupted else 1)
                # The leaked worker inherits stdout. Do not wait for pipe EOF.
                if terminal:
                    drain_terminal()
                    output = captured.decode(errors='replace')
                else:
                    os.set_blocking(process.stdout.fileno(), False)
                    output = process.stdout.read().decode(errors='replace')
                self.assertTrue(ready.exists(), 'worker did not reach ready state')
                records = list((state / 'mtk/jobs').glob('*.json'))
                self.assertTrue(records, 'failure occurred before tracking was persisted')
                for path in records:
                    record = json.loads(path.read_text())
                    known.update({int(pid): tuple(identity)
                                  for pid, identity in record['members'].items()})
                pid = int(ready.read_text())
                identity = jobs.process_identity(pid)
                if identity:
                    known[pid] = identity
                self.assertIn('injected persistent ps snapshot failure', output)
                if interrupted and not standalone:
                    self.assertIn('incomplete log:', output)
                if terminal:
                    flags = termios.ECHO | termios.ICANON
                    self.assertEqual(termios.tcgetattr(master)[3] & flags, baseline[3] & flags,
                                     'MTK left terminal in raw mode after snapshot failure')
                self.assertIsNone(identity, 'MTK leaked the tracked workload after ps failed')
            finally:
                # Also collect fixture-owned PIDs when an earlier assertion failed.
                for path in (state / 'mtk/jobs').glob('*.json'):
                    record = json.loads(path.read_text())
                    known.update({int(pid): tuple(identity)
                                  for pid, identity in record['members'].items()})
                if ready.exists():
                    pid = int(ready.read_text())
                    identity = jobs.process_identity(pid)
                    if identity:
                        known[pid] = identity
                if process is not None and process.poll() is None:
                    process.kill()
                for pid, identity in known.items():
                    if identity[0] == os.getuid() and jobs.process_identity(pid) == identity:
                        try:
                            os.kill(pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline and any(
                        jobs.process_identity(pid) == identity for pid, identity in known.items()):
                    time.sleep(0.02)
                survivors = [pid for pid, identity in known.items()
                             if jobs.process_identity(pid) == identity]
                if process is not None and process.stdout is not None:
                    process.stdout.close()
                if process is not None:
                    process.wait(timeout=3)
                for fd in (master, slave):
                    if fd is not None:
                        os.close(fd)
                self.assertFalse(survivors, 'fixture cleanup failed')

    def test_source_output_terminates_workload_when_ps_fails(self):
        self.exercise()

    def test_standalone_runner_terminates_workload_when_ps_fails(self):
        self.exercise(standalone=True)

    def test_runner_preserves_sigterm_when_snapshot_is_interrupted(self):
        self.exercise(standalone=True, interrupted=True)

    def test_output_preserves_sigterm_when_snapshot_is_interrupted(self):
        for terminal in (False, True):
            with self.subTest(terminal=terminal):
                self.exercise(terminal=terminal, interrupted=True)

    def test_terminal_restored_when_ps_fails(self):
        self.exercise(terminal=True)

if __name__ == '__main__':
    unittest.main(verbosity=2)
