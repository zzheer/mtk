"""Current-user MTK jobs. Polling cannot capture detach/reparent between samples."""
import contextlib
import ctypes
import fcntl
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from typing import ClassVar


class _BSDInfo(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, type]]] = [(name, ctypes.c_uint32) for name in (
        'flags', 'status', 'xstatus', 'pid', 'ppid', 'uid', 'gid', 'ruid',
        'rgid', 'svuid', 'svgid', 'rfu')]
    _fields_ += [('comm', ctypes.c_char * 16), ('name', ctypes.c_char * 32)]
    _fields_ += [(name, ctypes.c_uint32) for name in (
        'nfiles', 'pgid', 'pjobc', 'e_tdev', 'e_tpgid')]
    _fields_ += [('nice', ctypes.c_int32), ('start_sec', ctypes.c_uint64),
                ('start_usec', ctypes.c_uint64)]


_LIBPROC = ctypes.CDLL('/usr/lib/libproc.dylib') if sys.platform == 'darwin' else None
if _LIBPROC:
    _LIBPROC.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                                    ctypes.c_void_p, ctypes.c_int]
    _LIBPROC.proc_pidinfo.restype = ctypes.c_int


def process_identity(pid):
    """Return (uid, birth_seconds, birth_fraction), or None for missing/zombie."""
    if _LIBPROC:
        info = _BSDInfo()
        size = ctypes.sizeof(info)
        if _LIBPROC.proc_pidinfo(pid, 3, 0, ctypes.byref(info), size) != size or info.status == 5:
            return None
        return (info.uid, info.start_sec, info.start_usec)
    try:
        path = Path('/proc') / str(pid)
        stat = (path / 'stat').read_text().rsplit(')', 1)[1].split()
        if stat[0] == 'Z':
            return None
        # /proc starttime is monotonic ticks since boot; boot id prevents reboot reuse.
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        return (path.stat().st_uid, boot, int(stat[19]))
    except (OSError, ValueError, IndexError):
        return None


def process_table():
    """One bounded snapshot of pid -> (parent pid, process group)."""
    output = subprocess.check_output(['ps', '-axo', 'pid=,ppid=,pgid='], text=True, timeout=3)
    return {int(pid): (int(parent), int(group)) for pid, parent, group in
            (line.split() for line in output.splitlines() if len(line.split()) == 3)}


def manager_ancestors():
    table = process_table()
    pid = os.getpid()
    excluded = {1}
    while pid > 1 and pid not in excluded:
        excluded.add(pid)
        pid = table.get(pid, (0, 0))[0]
    return excluded


def _directory():
    base = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local' / 'state')
    path = base / 'mtk' / 'jobs'
    for directory in (path.parent, path):
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if directory.is_symlink() or directory.stat().st_uid != os.getuid():
            raise OSError('MTK job state must be owned by the current user')
        directory.chmod(0o700)
    return path


@contextlib.contextmanager
def _locked():
    directory = _directory()
    fd = os.open(directory / '.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError('MTK job lock must be a regular file')
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield directory
    finally:
        os.close(fd)


def _read_record(path):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise OSError('MTK job record must be a current-user regular file')
        if info.st_size > 65536:
            raise OSError('MTK job record exceeds 64 KiB')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read(65537)
        if len(data) > 65536:
            raise OSError('MTK job record exceeds 64 KiB')
        return json.loads(data)
    finally:
        os.close(fd)


def prepare_state():
    """Verify private, writable state before starting a workload."""
    with _locked() as directory:
        fd, path = tempfile.mkstemp(prefix='.', dir=directory)
        os.close(fd)
        Path(path).unlink()


class Tracker:
    def __init__(self, root_pid, command, persist=True):
        self.id = str(uuid.uuid4())
        self.root_pid = root_pid
        self.command = list(command)
        self.persist = persist
        self.members = {}
        identity = process_identity(root_pid)
        if identity and identity[0] == os.getuid():
            self.members[root_pid] = identity
        self.root_identity = identity
        self.refresh()

    def refresh(self):
        self.members = {pid: identity for pid, identity in self.members.items()
                        if process_identity(pid) == identity and identity[0] == os.getuid()}
        table = process_table()
        witness = self._group_witness(table)
        group = self.root_pid if witness else None
        pending = set(self.members)
        while pending:
            discovered = set()
            for pid, (parent, pgid) in table.items():
                if pid in self.members or not (parent in pending or (group is not None and pgid == group)):
                    continue
                identity = process_identity(pid)
                if parent in pending and process_identity(parent) != self.members[parent]:
                    continue
                if group is not None and pgid == group and process_identity(witness[0]) != witness[1]:
                    continue
                if identity and identity[0] == os.getuid():
                    self.members[pid] = identity
                    discovered.add(pid)
            pending = discovered
        if self.persist:
            self._save()
        return bool(self.members)

    def _group_witness(self, table, excluded=()):
        # A surviving verified member keeps the original private group identifiable.
        if any(table.get(pid, (0, None))[1] == self.root_pid for pid in excluded):
            return None
        for pid, identity in self.members.items():
            if (identity[0] == os.getuid() and
                    table.get(pid, (0, None))[1] == self.root_pid and
                    process_identity(pid) == identity):
                return pid, identity
        return None

    def signal(self, sig, excluded=()):
        # Emergency signaling must remain available when ps discovery fails.
        excluded = set(excluded)
        table = {}
        for pid in set(self.members) | excluded:
            try:
                table[pid] = (0, os.getpgid(pid))
            except ProcessLookupError:
                pass
        witness = self._group_witness(table, excluded)
        group_sent = False
        if witness and process_identity(witness[0]) == witness[1]:
            try:
                os.killpg(self.root_pid, sig)
                group_sent = True
            except ProcessLookupError:
                pass
        for pid, identity in list(self.members.items()):
            if group_sent and table.get(pid, (0, None))[1] == self.root_pid:
                continue
            if pid not in excluded and identity[0] == os.getuid() and process_identity(pid) == identity:
                try:
                    os.kill(pid, sig)
                except ProcessLookupError:
                    pass

    def finish(self):
        self.refresh()

    def _data(self):
        return {'id': self.id, 'uid': os.getuid(), 'root_pid': self.root_pid,
                'root_identity': self.root_identity, 'command': self.command,
                'members': {str(pid): identity for pid, identity in self.members.items()}}

    def _write(self, directory):
        path = directory / (self.id + '.json')
        if not self.members:
            path.unlink(missing_ok=True)
            return
        data = json.dumps(self._data()).encode()
        if len(data) > 65536:
            raise OSError('MTK job record exceeds 64 KiB')
        fd, temporary = tempfile.mkstemp(prefix='.', dir=directory)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def _save(self):
        with _locked() as directory:
            path = directory / (self.id + '.json')
            # A manager may have discovered descendants since the writer sampled.
            if path.exists():
                previous = self._load(_read_record(path))
                for pid, identity in previous.members.items():
                    if process_identity(pid) == identity:
                        self.members[pid] = identity
            self.members = {pid: identity for pid, identity in self.members.items()
                            if process_identity(pid) == identity}
            self._write(directory)

    @classmethod
    def _load(cls, data):
        if data['uid'] != os.getuid() or str(uuid.UUID(data['id'])) != data['id']:
            raise ValueError('invalid job owner or id')
        tracker = cls.__new__(cls)
        tracker.id = data['id']
        tracker.root_pid = int(data['root_pid'])
        tracker.root_identity = tuple(data['root_identity']) if data['root_identity'] else None
        tracker.command = data['command']
        tracker.members = {int(pid): tuple(identity) for pid, identity in data['members'].items()}
        tracker.persist = False
        return tracker


def active_jobs():
    jobs = []
    with _locked() as directory:
        for path in directory.glob('*.json'):
            if path.is_symlink() or path.stat().st_uid != os.getuid():
                continue
            tracker = Tracker._load(_read_record(path))
            alive = tracker.refresh()
            tracker._write(directory)
            if alive:
                jobs.append(tracker)
    return jobs


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv not in (['jobs'], ['stop', '--all']):
        print('usage: mtk jobs | mtk stop --all', file=sys.stderr)
        return 2
    try:
        jobs = active_jobs()
        if argv == ['jobs']:
            if not jobs:
                print('No active MTK jobs.')
            for job in jobs:
                print(f'{job.id} pids={",".join(map(str, sorted(job.members)))} {" ".join(job.command)}')
            return 0
        excluded = manager_ancestors()
        for job in jobs:
            job.signal(signal.SIGTERM, excluded)
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            for job in jobs:
                job.refresh()
            if not any(set(job.members) - excluded for job in jobs):
                break
            time.sleep(0.05)
        for job in jobs:
            job.refresh()
            job.signal(signal.SIGKILL, excluded)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            for job in jobs:
                job.refresh()
            if not any(set(job.members) - excluded for job in jobs):
                break
            time.sleep(0.05)
        survivors = sum(len(set(job.members) - excluded) for job in jobs)
        # Refresh private records only once termination has finished.
        for job in jobs:
            job.persist = True
            job.finish()
        if survivors:
            print(f'mtk: failed to stop {survivors} processes', file=sys.stderr)
            return 1
        print(f'Stopped {len(jobs)} MTK jobs.')
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as exc:
        print(f'mtk: job management failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
