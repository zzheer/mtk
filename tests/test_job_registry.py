import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'libexec' / 'mtk_jobs.py'

class JobsTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('mtk_jobs', MODULE)
        self.jobs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.jobs)
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'XDG_STATE_HOME': self.temp.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(self.temp.cleanup)

    def test_process_identity_distinguishes_process_and_user(self):
        identity = self.jobs.process_identity(os.getpid())
        self.assertEqual(identity[0], os.getuid())
        self.assertEqual(identity, self.jobs.process_identity(os.getpid()))
        self.assertIsNone(self.jobs.process_identity(2147483647))

    def test_reused_pid_is_neither_signalled_nor_discovery_root(self):
        identities = {900001: (os.getuid(), 1, 1)}
        with patch.object(self.jobs, 'process_identity', side_effect=identities.get), patch.object(self.jobs, 'process_table', return_value={900001: (0, 900001)}) as table:
            tracker = self.jobs.Tracker(900001, ['sleep', '10'])
            identities[900001] = (os.getuid(), 2, 2)
            with patch.object(self.jobs.os, 'kill') as kill:
                tracker.signal(signal.SIGTERM)
                kill.assert_not_called()
            tracker.refresh()
            self.assertFalse(tracker.members)

    def test_orphan_retained_and_later_pruned(self):
        identities = {900001: (os.getuid(), 1, 1), 900002: (os.getuid(), 1, 2)}
        with patch.object(self.jobs, 'process_identity', side_effect=identities.get), patch.object(self.jobs, 'process_table', return_value={900001: (0, 900001), 900002: (900001, 900001)}):
            tracker = self.jobs.Tracker(900001, ['sleep', '10'])
            tracker.refresh()
            del identities[900001]
            tracker.finish()
            jobs = self.jobs.active_jobs()
            self.assertEqual(len(jobs), 1)
            self.assertIn(900002, jobs[0].members)
            record = next((Path(self.temp.name) / 'mtk' / 'jobs').glob('*.json'))
            self.assertEqual(record.stat().st_mode & 0o777, 0o600)
            identities.clear()
            self.assertEqual(self.jobs.active_jobs(), [])
            self.assertFalse(record.exists())

    def test_nonpersistent_tracker_never_creates_record(self):
        with patch.object(self.jobs, 'process_identity', return_value=(os.getuid(), 1, 1)), patch.object(self.jobs, 'process_table', return_value={}):
            tracker = self.jobs.Tracker(900001, ['sleep'], persist=False)
            tracker.refresh()
            tracker.finish()
            self.assertFalse((Path(self.temp.name) / 'mtk' / 'jobs').exists())

    def test_stop_all_escalates_and_leaves_unrelated_process_alive(self):
        command = [sys.executable, '-c',
                   'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print("ready",flush=True); time.sleep(20)']
        child = subprocess.Popen(command, start_new_session=True, stdout=subprocess.PIPE, text=True)
        other = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'], start_new_session=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), 'ready')
            self.jobs.Tracker(child.pid, command)
            self.assertEqual(self.jobs.main(['stop', '--all']), 0)
            child.wait(timeout=3)
            self.assertEqual(child.returncode, -signal.SIGKILL)
            self.assertIsNone(other.poll())
            self.assertEqual(self.jobs.active_jobs(), [])
        finally:
            for process in (child, other):
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=3)
            child.stdout.close()

    def test_shared_group_does_not_adopt_unrelated_process(self):
        identities = {900001: (os.getuid(), 1, 1), 900002: (os.getuid(), 1, 2)}
        with patch.object(self.jobs, 'process_identity', side_effect=identities.get), patch.object(self.jobs, 'process_table', return_value={900001: (77, 77), 900002: (77, 77)}):
            tracker = self.jobs.Tracker(900001, ['sleep'], persist=False)
            self.assertEqual(set(tracker.members), {900001})

    def test_group_signal_is_not_sent_twice_to_group_members(self):
        identities = {900001: (os.getuid(), 1, 1), 900002: (os.getuid(), 1, 2),
                      900003: (os.getuid(), 1, 3)}
        table = {900001: (77, 900001), 900002: (900001, 900001),
                 900003: (900001, 900003)}
        with patch.object(self.jobs, 'process_identity', side_effect=identities.get), \
             patch.object(self.jobs, 'process_table', return_value=table):
            tracker = self.jobs.Tracker(900001, ['sleep'], persist=False)
            with patch.object(self.jobs.os, 'getpgid', side_effect=lambda pid: table[pid][1]), \
                 patch.object(self.jobs.os, 'killpg') as group_signal, \
                 patch.object(self.jobs.os, 'kill') as individual_signal:
                tracker.signal(signal.SIGINT)
                group_signal.assert_called_once_with(900001, signal.SIGINT)
                self.assertEqual(individual_signal.call_args_list,
                                 [unittest.mock.call(900003, signal.SIGINT)])

    def test_record_reads_reject_nonregular_and_oversized_files(self):
        directory = Path(self.temp.name)
        fifo = directory / 'fifo'
        os.mkfifo(fifo)
        with self.assertRaises(OSError):
            self.jobs._read_record(fifo)
        large = directory / 'large'
        large.write_bytes(b'x' * 65537)
        with self.assertRaises(OSError):
            self.jobs._read_record(large)

    def test_real_detached_orphan_survives_root_exit_and_is_stopped(self):
        child_code = 'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(20)'
        root_code = ('import subprocess,sys,time; time.sleep(.1); '
                     'p=subprocess.Popen([sys.executable,"-c",sys.argv[1]],start_new_session=True); '
                     'print(p.pid,flush=True); time.sleep(.3)')
        command = [sys.executable, '-c', root_code, child_code]
        root = subprocess.Popen(command, start_new_session=True, stdout=subprocess.PIPE, text=True)
        orphan = None
        try:
            tracker = self.jobs.Tracker(root.pid, command)
            orphan = int(root.stdout.readline())
            tracker.refresh()
            self.assertIn(orphan, tracker.members)
            root.wait(timeout=3)
            tracker.finish()
            self.assertTrue(any(orphan in job.members for job in self.jobs.active_jobs()))
            self.assertEqual(self.jobs.main(['stop', '--all']), 0)
            self.assertIsNone(self.jobs.process_identity(orphan))
        finally:
            if root.poll() is None:
                root.kill()
            root.wait(timeout=3)
            root.stdout.close()
            if orphan and self.jobs.process_identity(orphan):
                os.kill(orphan, signal.SIGKILL)

    def test_oversized_record_rejected_without_replacing_valid_record(self):
        with patch.object(self.jobs, 'process_identity', return_value=(os.getuid(), 1, 1)), patch.object(self.jobs, 'process_table', return_value={}):
            tracker = self.jobs.Tracker(900001, ['sleep'])
            record = Path(self.temp.name) / 'mtk' / 'jobs' / (tracker.id + '.json')
            original = record.read_bytes()
            tracker.command = ['python3', '-c', 'x' * 65536]
            with self.assertRaisesRegex(OSError, '64 KiB'):
                tracker.refresh()
            self.assertEqual(record.read_bytes(), original)

    def test_signalling_excludes_current_manager_ancestor_chain(self):
        identities = {900001: (os.getuid(), 1, 1), 900002: (os.getuid(), 1, 2), 900003: (os.getuid(), 1, 3)}
        table = {900001: (1, 900001), 900002: (900001, 900002), 900003: (1, 900001)}
        with patch.object(self.jobs, 'process_identity', side_effect=identities.get), patch.object(self.jobs, 'process_table', return_value=table):
            tracker = self.jobs.Tracker(900002, ['manager-parent'], persist=False)
            with patch.object(self.jobs.os, 'getpid', return_value=900002), patch.object(self.jobs.os, 'kill') as kill:
                tracker.signal(signal.SIGTERM, self.jobs.manager_ancestors())
                kill.assert_not_called()
            self.assertNotIn(900003, tracker.members)

    def test_group_discovery_continues_after_original_leader_exits(self):
        identities = {900001: (os.getuid(), 1, 1), 900002: (os.getuid(), 1, 2)}
        table = {900001: (1, 900001), 900002: (900001, 900001)}
        with patch.object(self.jobs, 'process_identity', side_effect=identities.get), patch.object(self.jobs, 'process_table', side_effect=lambda: dict(table)):
            tracker = self.jobs.Tracker(900001, ['sleep'], persist=False)
            del identities[900001]
            del table[900001]
            identities[900003] = (os.getuid(), 1, 3)
            table[900002] = (1, 900001)
            table[900003] = (1, 900001)
            tracker.refresh()
            self.assertEqual(set(tracker.members), {900002, 900003})
            identities[900002] = (os.getuid(), 2, 2)
            identities[900003] = (os.getuid(), 2, 3)
            identities[900004] = (os.getuid(), 2, 4)
            table[900004] = (1, 900001)
            tracker.refresh()
            self.assertFalse(tracker.members)

    def test_group_signal_is_suppressed_when_excluded_ancestor_in_group(self):
        identities = {900001: (os.getuid(), 1, 1), 900002: (os.getuid(), 1, 2)}
        table = {900001: (1, 900001), 900002: (900001, 900001)}
        with patch.object(self.jobs, 'process_identity', side_effect=identities.get), patch.object(self.jobs, 'process_table', return_value=table):
            tracker = self.jobs.Tracker(900001, ['sleep'], persist=False)
            with patch.object(self.jobs.os, 'getpgid', side_effect=lambda pid: table[pid][1]), patch.object(self.jobs.os, 'killpg') as group_kill, patch.object(self.jobs.os, 'kill') as kill:
                tracker.signal(signal.SIGTERM, {900001})
                group_kill.assert_not_called()
                kill.assert_called_once_with(900002, signal.SIGTERM)

    def test_group_signal_covers_real_child_forked_since_refresh(self):
        root_code = ('import subprocess,sys,time; sys.stdin.readline(); '
                     'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(20)"]); '
                     'print(p.pid,flush=True); time.sleep(20)')
        command = [sys.executable, '-c', root_code]
        root = subprocess.Popen(command, start_new_session=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        child = None
        try:
            tracker = self.jobs.Tracker(root.pid, command, persist=False)
            root.stdin.write('spawn\n')
            root.stdin.flush()
            child = int(root.stdout.readline())
            self.assertNotIn(child, tracker.members)
            tracker.signal(signal.SIGKILL)
            root.wait(timeout=3)
            deadline = time.monotonic() + 2
            while self.jobs.process_identity(child) and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertIsNone(self.jobs.process_identity(child))
        finally:
            if root.poll() is None:
                root.kill()
            root.wait(timeout=3)
            root.stdin.close()
            root.stdout.close()
            if child and self.jobs.process_identity(child):
                os.kill(child, signal.SIGKILL)

    def test_group_witness_is_rechecked_immediately_before_signalling(self):
        identity = (os.getuid(), 1, 1)
        reused = (os.getuid(), 2, 2)
        with patch.object(self.jobs, 'process_identity', return_value=identity), patch.object(self.jobs, 'process_table', return_value={900001: (1, 900001)}):
            tracker = self.jobs.Tracker(900001, ['sleep'], persist=False)
            with patch.object(self.jobs.os, 'getpgid', return_value=900001), patch.object(self.jobs, 'process_identity', side_effect=[identity, reused, reused]), patch.object(self.jobs.os, 'killpg') as group_kill, patch.object(self.jobs.os, 'kill') as kill:
                tracker.signal(signal.SIGTERM)
                group_kill.assert_not_called()
                kill.assert_not_called()

    def test_manager_ancestors_are_excluded(self):
        with patch.object(self.jobs, 'process_table', return_value={100: (90, 100), 90: (80, 90), 80: (1, 80)}), patch.object(self.jobs.os, 'getpid', return_value=100):
            self.assertTrue({100, 90, 80}.issubset(self.jobs.manager_ancestors()))

if __name__ == '__main__':
    unittest.main()
