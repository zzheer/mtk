"""Real-process outer initial discovery failure; fixture files stay outside checkout."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest

sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fixture_jobs', SOURCE / 'libexec/mtk_jobs.py')
jobs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jobs)


def exercise_startup_failure(delay_inner_snapshot):
    with tempfile.TemporaryDirectory(prefix='mtk-startup-regression-') as directory:
        folder = Path(directory)
        shim = folder / 'ps'
        shim.write_text('#!' + sys.executable + '\n' + textwrap.dedent('''\
            import os, pathlib, signal, sys, time
            folder = pathlib.Path(os.environ["FIXTURE_DIRECTORY"])
            deadline = time.monotonic() + 5
            while not (folder / "outer").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            outer = int((folder / "outer").read_text())
            if os.getppid() == outer:
                while not (folder / "ready").exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                if not (folder / "ready").exists():
                    sys.exit(74)
                time.sleep(0.5)
                print("injected outer initial ps failure after worker READY", file=sys.stderr)
                sys.exit(73)
            delay = float(os.environ["DELAY_INNER_SNAPSHOT"])
            if delay:
                if delay > 2:
                    signal.signal(signal.SIGTERM, signal.SIG_IGN)
                time.sleep(delay)
            os.execv("/bin/ps", ["/bin/ps"] + sys.argv[1:])
        '''))
        shim.chmod(0o700)
        worker = folder / 'worker.py'
        worker.write_text('import json, os, pathlib, signal, time\n'
                          'signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
                          'pathlib.Path(os.environ["FIXTURE_DIRECTORY"], "ready").write_text('
                          'json.dumps({"worker": os.getpid(), "governor": os.getppid()}))\n'
                          'time.sleep(20)\n')
        env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
               'PATH': str(folder) + os.pathsep + os.environ['PATH'],
               'FIXTURE_DIRECTORY': str(folder),
               'DELAY_INNER_SNAPSHOT': str(delay_inner_snapshot),
               'XDG_STATE_HOME': str(folder / 'state'),
               'XDG_CONFIG_HOME': str(folder / 'config')}
        command = [sys.executable, str(SOURCE / 'libexec/mtk-output.py'),
                   str(SOURCE / 'bin/mtk'), '--time-limit', '8s', sys.executable, str(worker)]
        process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        known = {process.pid: jobs.process_identity(process.pid)}
        (folder / 'outer').write_text(str(process.pid))
        try:
            deadline = time.monotonic() + 6
            while not (folder / 'ready').exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert (folder / 'ready').exists(), 'worker never became ready'
            pids = json.loads((folder / 'ready').read_text())
            for pid in pids.values():
                known[pid] = jobs.process_identity(pid)
            assert all(known[pid] for pid in pids.values()), 'fixture missed live worker/governor identities'
            process.wait(timeout=15)
            leaked = jobs.process_identity(pids['worker']) == known[pids['worker']]
            assert process.returncode == 1, process.returncode
            assert not leaked, 'governed worker survived outer initial discovery failure'
        finally:
            for pid, identity in known.items():
                if identity and jobs.process_identity(pid) == identity:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            process.wait(timeout=3)
            _, stderr = process.communicate(timeout=3)
            deadline = time.monotonic() + 3
            while any(identity and jobs.process_identity(pid) == identity
                      for pid, identity in known.items()) and time.monotonic() < deadline:
                time.sleep(0.02)
            survivors = [pid for pid, identity in known.items()
                         if identity and jobs.process_identity(pid) == identity]
            assert not survivors, 'fixture cleanup left survivors'
        assert b'incomplete log:' in stderr, stderr
        assert b'injected outer initial ps failure' in stderr, stderr


class StartupDiscoveryRegression(unittest.TestCase):
    def test_initial_outer_discovery_failure_cleans_governed_worker(self):
        exercise_startup_failure(0)

    def test_initial_outer_discovery_failure_during_governor_initial_snapshot(self):
        exercise_startup_failure(2)

    def test_initial_outer_discovery_failure_allows_near_timeout_cleanup_snapshots(self):
        exercise_startup_failure(2.8)


if __name__ == '__main__':
    unittest.main(verbosity=2)
