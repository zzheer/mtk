import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
MTK = str(ROOT / 'bin/mtk')


class JobsTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.env = {**os.environ, 'XDG_STATE_HOME': str(self.folder / 'state'),
                    'XDG_CONFIG_HOME': str(self.folder / 'config'),
                    'PYTHONDONTWRITEBYTECODE': '1'}

    def invoke(self, *args):
        result = subprocess.run([MTK, *args], env=self.env, capture_output=True,
                                text=True, timeout=10)
        for path in re.findall(r'(?m)^(/tmp/mtk-[^\r\n]+\.log)$', result.stderr):
            self.addCleanup(Path(path).unlink, missing_ok=True)
        return result

    def test_corrupt_live_record_terminates_workload(self):
        for command in ([MTK], [sys.executable, str(ROOT / 'libexec/mtk-runner.py'), '--']):
            with self.subTest(command=command):
                env = dict(self.env)
                env.pop('MTK_JOB_CAPTURED', None)
                process = subprocess.Popen([*command, sys.executable, '-c',
                    'import os,time; print(os.getpid(),flush=True); time.sleep(10)'],
                    env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                pid = None
                try:
                    pid = int(process.stdout.readline())
                    deadline = time.monotonic() + 3
                    records = []
                    while not records and time.monotonic() < deadline:
                        records = list((self.folder / 'state/mtk/jobs').glob('*.json'))
                        time.sleep(0.02)
                    self.assertTrue(records, 'no workload record')
                    for record in records:
                        record.write_text('{')
                    process.wait(timeout=4)
                    status = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)],
                        capture_output=True, text=True, timeout=3).stdout.strip()
                    self.assertTrue(not status or status.startswith('Z'),
                                    f'workload survived registry failure: {status}')
                    self.assertNotEqual(process.returncode, 0)
                finally:
                    if pid:
                        try:
                            os.kill(pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    if process.poll() is None:
                        process.kill()
                    process.communicate(timeout=3)
                    for record in (self.folder / 'state/mtk/jobs').glob('*.json'):
                        record.unlink()

    def test_oversized_command_record_does_not_leak_workload(self):
        env = dict(self.env)
        env.pop('MTK_JOB_CAPTURED', None)
        code = 'import os,time; print(os.getpid(),flush=True); time.sleep(10) #' + 'x' * 65536
        process = subprocess.Popen([sys.executable, str(ROOT / 'libexec/mtk-runner.py'),
            '--time-limit', '8s', '--', sys.executable, '-c', code], env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        pid = None
        try:
            stdout = process.stdout.readline()
            process.wait(timeout=3)
            self.assertNotEqual(process.returncode, 0)
            if stdout.strip():
                pid = int(stdout.strip())
                status = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)],
                    capture_output=True, text=True, timeout=3).stdout.strip()
                self.assertTrue(not status or status.startswith('Z'),
                                f'workload survived initial registry failure: {status}')
        finally:
            if pid:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=3)

    def test_empty_jobs_is_successful(self):
        result = self.invoke('jobs')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('No active', result.stdout)

    def test_stop_all_with_no_jobs_is_successful(self):
        result = self.invoke('stop', '--all')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_management_commands_validate_requested_limits(self):
        result = self.invoke('jobs', '--cpu-limit', '0')
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_proxy_command_executes_under_legacy_prefixes(self):
        for prefix in ([], ['--verbose'], ['--ultra-compact']):
            with self.subTest(prefix=prefix):
                result = self.invoke(*prefix, 'proxy', sys.executable, '-c', "print('PROXY_RAN')")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('PROXY_RAN', result.stdout)

    def test_stop_all_kills_resistant_workload_and_child_without_killing_unrelated_process(self):
        ready = self.folder / 'ready'
        script = self.folder / 'workload.py'
        script.write_text('import os, signal, subprocess, sys, time\n'
            'signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
            'child = subprocess.Popen([sys.executable, "-c", '
            '"import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"])\n'
            'open(sys.argv[1], "w").write(f"{os.getpid()} {child.pid}")\n'
            'time.sleep(30)\n')
        workload = subprocess.Popen([MTK, sys.executable, str(script), str(ready)],
            env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
        unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        pids = []
        try:
            deadline = time.monotonic() + 5
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(ready.exists(), 'workload did not start')
            pids = [int(pid) for pid in ready.read_text().split()]
            listing = self.invoke('jobs')
            self.assertEqual(listing.returncode, 0, listing.stderr)
            self.assertIn('workload.py', listing.stdout)
            stopped = self.invoke('stop', '--all')
            self.assertEqual(stopped.returncode, 0, stopped.stderr)
            workload.wait(timeout=5)
            for pid in pids:
                status = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)],
                    capture_output=True, text=True, timeout=3).stdout.strip()
                self.assertTrue(not status or status.startswith('Z'), f'{pid} survived: {status}')
            self.assertIsNone(unrelated.poll())
            self.assertIn('No active', self.invoke('jobs').stdout)
        finally:
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            for process in (workload, unrelated):
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
