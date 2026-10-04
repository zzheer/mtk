import importlib.util
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


RUNNER = Path(__file__).resolve().parents[1] / "libexec" / "mtk-runner.py"
spec = importlib.util.spec_from_file_location("mtk_runner", RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class GovernorTests(unittest.TestCase):
    def test_rejected_cpu_limit_fails_before_workload(self):
        result = self.run_command(["--cpu-limit", "999999"], "print('MUST_NOT_RUN')")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertNotIn("MUST_NOT_RUN", result.stdout)

    def test_limiter_exit_terminates_workload(self):
        with tempfile.TemporaryDirectory() as folder:
            package = Path(folder)
            shutil.copy2(RUNNER, package / "mtk-runner.py")
            helper = package / "mtk-cpulimit"
            helper.write_text("#!/bin/sh\nsleep 0.1\nexit 9\n")
            helper.chmod(0o755)
            result = subprocess.run([sys.executable, str(package / "mtk-runner.py"),
                "--cpu-limit", "20", "--", sys.executable, "-c",
                "import time; time.sleep(2); print('MUST_NOT_COMPLETE')"],
                capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 127, result.stderr)
            self.assertIn("CPU limiter exited", result.stderr)
            self.assertNotIn("MUST_NOT_COMPLETE", result.stdout)

    def test_packaged_cpulimit_resolves_with_isolated_home(self):
        with tempfile.TemporaryDirectory() as folder:
            package = Path(folder) / "libexec"
            package.mkdir()
            helper = package / "mtk-cpulimit"
            helper.write_text("#!/bin/sh\nexit 0\n")
            helper.chmod(0o755)
            with mock.patch.object(runner, "__file__", str(package / "mtk-runner.py")), \
                 mock.patch.dict(os.environ, {"HOME": folder, "PATH": ""}):
                self.assertEqual(runner.find_cpulimit_bin(), str(helper.resolve()))

    def run_command(self, options, code, timeout=8):
        return subprocess.run(
            [sys.executable, str(RUNNER), *options, "--", sys.executable, "-c", code],
            capture_output=True, text=True, timeout=timeout,
        )

    def test_timeout_status(self):
        result = self.run_command(["--time-limit", "0.2s"], "import time; time.sleep(5)")
        self.assertEqual(result.returncode, 124, result.stderr)

    def test_memory_status_with_time_limit(self):
        result = self.run_command(
            ["--memory-limit", "30M", "--time-limit", "5s"],
            "import time; x=bytearray(60*1024*1024); time.sleep(6)",
        )
        self.assertEqual(result.returncode, 137, result.stderr)

    def test_signal_status(self):
        result = self.run_command([], "import os, signal; os.kill(os.getpid(), signal.SIGTERM)")
        self.assertEqual(result.returncode, 143, result.stderr)

    def test_singleton_wait(self):
        self.check_singleton(wait=True)

    def test_singleton_replacement_finishes_cleanup(self):
        self.check_singleton(wait=False)

    def check_singleton(self, wait):
        with tempfile.TemporaryDirectory() as folder:
            ready = Path(folder) / "ready"
            env = dict(os.environ, MTK_LOCK_DIR=folder)
            code = f"import time; open({str(ready)!r}, 'w').write('ready'); time.sleep({0.5 if wait else 6})"
            first = subprocess.Popen(
                [sys.executable, str(RUNNER), "--singleton", "test", "--", sys.executable, "-c", code],
                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            try:
                deadline = time.monotonic() + 2
                while not ready.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(ready.exists(), "singleton workload did not start")
                flag = "--singleton-wait" if wait else "--singleton"
                second = subprocess.run(
                    [sys.executable, str(RUNNER), flag, "test", "--", sys.executable, "-c", "pass"],
                    env=env, capture_output=True, text=True, timeout=5,
                )
                self.assertEqual(second.returncode, 0, second.stderr)
                self.assertEqual(first.wait(timeout=2), 0 if wait else 143)
            finally:
                if first.poll() is None:
                    first.terminate()
                    first.wait(timeout=3)

    def test_missing_cpulimit_fails_before_command(self):
        with mock.patch.object(runner, "find_cpulimit_bin", return_value=None), \
             mock.patch.object(sys, "argv", [str(RUNNER), "--cpu-limit", "20", "--", "unused"]), \
             mock.patch.object(runner.subprocess, "Popen") as popen:
            with self.assertRaises(SystemExit) as raised:
                runner.main()
            self.assertEqual(raised.exception.code, 127)
            popen.assert_not_called()

    def test_timeout_kills_stubborn_detached_descendant(self):
        self.check_stubborn_descendant(["--time-limit", "0.6s"], 124)

    def test_memory_kills_stubborn_detached_descendant(self):
        self.check_stubborn_descendant(["--memory-limit", "45M", "--time-limit", "5s"], 137, allocate=True)

    def check_stubborn_descendant(self, options, expected, allocate=False):
        with tempfile.TemporaryDirectory() as folder:
            pid_file = Path(folder) / "pid"
            child_code = (
                "import os, signal, time; os.setsid(); "
                "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                f"open({str(pid_file)!r}, 'w').write(str(os.getpid())); "
                + ("x=bytearray(70*1024*1024); " if allocate else "")
                + "time.sleep(7)"
            )
            code = f"import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', {child_code!r}]); time.sleep(7)"
            pid = None
            try:
                started = time.monotonic()
                result = self.run_command(options, code)
                self.assertLess(time.monotonic() - started, 3.5, "cleanup waited for descendant's natural exit")
                pid = int(pid_file.read_text())
                self.assertEqual(result.returncode, expected, result.stderr)
                state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
                self.assertTrue(not state or state.startswith("Z"), f"descendant {pid} still running: {state}")
            finally:
                if pid is None and pid_file.exists():
                    pid = int(pid_file.read_text())
                if pid:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    @unittest.skipUnless(runner.find_cpulimit_bin(), "cpulimit unavailable")
    def test_cpu_limit_includes_children_by_default(self):
        measurements = []
        with tempfile.TemporaryDirectory() as folder:
            package = Path(folder) / "libexec"
            package.mkdir()
            packaged_runner = package / "mtk-runner.py"
            shutil.copy2(RUNNER, packaged_runner)
            shutil.copy2(runner.find_cpulimit_bin(), package / "mtk-cpulimit")
            env = dict(os.environ, HOME=folder, PATH="/usr/bin:/bin")
            for exclude in (False, True):
                output = Path(folder) / str(exclude)
                child_code = (
                    "import time; start=time.monotonic(); cpu=time.process_time(); "
                    "exec('while time.monotonic()-start < 2.5: pass'); "
                    f"open({str(output)!r}, 'w').write(str(time.process_time()-cpu))"
                )
                code = f"import subprocess, sys; subprocess.run([sys.executable, '-c', {child_code!r}])"
                options = ["--cpu-limit", "15", "--time-limit", "5s", "--memory-limit", "120M"]
                if exclude:
                    options.append("--exclude-children")
                result = subprocess.run(
                    [sys.executable, str(packaged_runner), *options, "--", sys.executable, "-c", code],
                    capture_output=True, text=True, timeout=8, env=env,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                measurements.append(float(output.read_text()))
            self.assertGreater(measurements[1], 0.8, measurements)
            self.assertLess(measurements[0], measurements[1] * 0.7, measurements)
            print(f"CPU seconds default={measurements[0]:.3f}, excluded={measurements[1]:.3f}")


if __name__ == "__main__":
    unittest.main()
