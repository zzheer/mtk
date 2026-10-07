import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RUNNER = str(Path(__file__).resolve().parents[1] / 'libexec/mtk-runner.py')
ROOT = Path(__file__).resolve().parents[1]


class DescendantCpuTests(unittest.TestCase):
    def test_cpu_history_resets_when_pid_is_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            binary = str(Path(folder) / 'identity-test')
            # Disable the old abort so a stale identity is reported as a test failure.
            built = subprocess.run(['cc', '-DNDEBUG', '-I', str(ROOT / 'vendor/cpulimit/src'),
                str(ROOT / 'tests/cpulimit_pid_reuse.c'),
                str(ROOT / 'vendor/cpulimit/src/process_group.c'),
                str(ROOT / 'vendor/cpulimit/src/list.c'), '-o', binary],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(built.returncode, 0, built.stderr)
            tested = subprocess.run([binary], capture_output=True, text=True, timeout=5)
            self.assertEqual(tested.returncode, 0, tested.stderr)

    def test_cpu_cap_applies_to_grandchild(self):
        with tempfile.TemporaryDirectory() as folder:
            result_path = Path(folder) / 'cpu'
            worker = ('import time; start=time.monotonic(); cpu=time.process_time(); '
                      "exec('while time.monotonic()-start < 2.5: pass'); "
                      f'open({str(result_path)!r}, "w").write(str(time.process_time()-cpu))')
            parent = f'import subprocess,sys; subprocess.run([sys.executable,"-c",{worker!r}])'
            root = f'import subprocess,sys; subprocess.run([sys.executable,"-c",{parent!r}])'
            completed = subprocess.run([sys.executable, RUNNER, '--cpu-limit', '15',
                '--time-limit', '6s', '--', sys.executable, '-c', root],
                env={**os.environ, 'XDG_STATE_HOME': str(Path(folder) / 'state')},
                capture_output=True, text=True, timeout=8)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertLess(float(result_path.read_text()), 0.9)


if __name__ == '__main__':
    unittest.main()
