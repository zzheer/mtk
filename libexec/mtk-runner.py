#!/usr/bin/env python3
"""Resource governor runner for mtk commands.

Enforces:
  --time-limit <duration>   (e.g., 30s, 5m, 1h, 120)
  --memory-limit <size>     (e.g., 500M, 2G, 4GiB, 1048576)
  --cpu-limit <pct>         (e.g., 50, 50%, 200)
  --singleton [id]          (terminates previous instance with up to 5 retries)
  --singleton-wait [id]     (waits for previous instance to exit)
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path


LOCK_DIR = Path(os.environ.get("MTK_LOCK_DIR", Path.home() / ".local/state/mtk/locks"))


def parse_duration(val: str) -> float:
    """Parse duration string like '30s', '5m', '2h', or '120' into seconds."""
    match = re.match(r"^(\d+(?:\.\d+)?)\s*([smhdw]?)$", val.strip().lower())
    if not match:
        raise ValueError(f"invalid duration: {val!r}")
    num, unit = match.groups()
    multiplier = {
        "": 1.0,
        "s": 1.0,
        "m": 60.0,
        "h": 3600.0,
        "d": 86400.0,
        "w": 604800.0,
    }[unit]
    return float(num) * multiplier


def parse_bytes(val: str) -> int:
    """Parse size string like '500M', '2G', '4GiB', or '1048576' into bytes."""
    match = re.match(r"^(\d+(?:\.\d+)?)\s*([kmgtpe]?i?b?)$", val.strip().lower())
    if not match:
        raise ValueError(f"invalid memory size: {val!r}")
    num, unit = match.groups()
    unit = unit.rstrip("b")
    units = {
        "": 1,
        "k": 1024,
        "ki": 1024,
        "m": 1024**2,
        "mi": 1024**2,
        "g": 1024**3,
        "gi": 1024**3,
        "t": 1024**4,
        "ti": 1024**4,
        "p": 1024**5,
        "pi": 1024**5,
    }
    if unit not in units:
        raise ValueError(f"unknown size unit in {val!r}")
    return int(float(num) * units[unit])


def parse_cpu(val: str) -> int:
    """Parse CPU limit string like '50', '50%' into integer percentage."""
    val = val.strip().rstrip("%")
    try:
        pct = int(val)
        if pct <= 0:
            raise ValueError
        return pct
    except ValueError:
        raise ValueError(f"invalid CPU percentage: {val!r}")


def get_process_tree_pids(root_pid: int) -> list[int]:
    """Find all descendant PIDs under root_pid on macOS."""
    pids = [root_pid]
    try:
        out = subprocess.check_output(
            ["pgrep", "-P", str(root_pid)], stderr=subprocess.DEVNULL, text=True
        )
        for line in out.strip().splitlines():
            child_pid = int(line.strip())
            pids.extend(get_process_tree_pids(child_pid))
    except (subprocess.CalledProcessError, ValueError):
        pass
    return pids


def get_process_tree_rss(root_pid: int) -> int:
    """Get total RSS in bytes across the process tree of root_pid."""
    pids = get_process_tree_pids(root_pid)
    total_rss_kb = 0
    try:
        pid_arg = ",".join(str(p) for p in pids)
        out = subprocess.check_output(
            ["ps", "-o", "rss=", "-p", pid_arg],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        for line in out.strip().splitlines():
            line = line.strip()
            if line:
                total_rss_kb += int(line)
    except (subprocess.CalledProcessError, ValueError):
        pass
    return total_rss_kb * 1024


def kill_process_tree(root_pid: int, sig: signal.Signals = signal.SIGTERM) -> None:
    """Send signal to entire process tree."""
    pids = get_process_tree_pids(root_pid)
    for p in reversed(pids):
        try:
            os.kill(p, sig)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass


def is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def handle_singleton(lock_name: str, wait_mode: bool) -> tuple[int, Path]:
    """Acquire singleton lock. If wait_mode is False, kill previous instance with up to 5 retries."""
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock_file = LOCK_DIR / f"{lock_name}.lock"
    fd = os.open(lock_file, os.O_RDWR | os.O_CREAT, 0o600)

    if wait_mode:
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, f"{os.getpid()}\n".encode())
        return fd, lock_file

    max_retries = 5
    for attempt in range(max_retries):
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.ftruncate(fd, 0)
            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, f"{os.getpid()}\n".encode())
            return fd, lock_file
        except BlockingIOError:
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                content = os.read(fd, 64).decode().strip()
                existing_pid = int(content) if content.isdigit() else None
            except Exception:
                existing_pid = None

            if existing_pid and existing_pid != os.getpid() and is_pid_alive(existing_pid):
                print(
                    f"mtk: singleton active instance (PID {existing_pid}) found; terminating (attempt {attempt + 1}/{max_retries})...",
                    file=sys.stderr,
                )
                try:
                    os.kill(existing_pid, signal.SIGTERM)
                except OSError:
                    pass
                # Allow the runner's one-second TERM/KILL cleanup to finish.
                time.sleep(1.5)

                if is_pid_alive(existing_pid):
                    try:
                        os.kill(existing_pid, signal.SIGKILL)
                    except OSError:
                        pass
                    time.sleep(0.2)
            else:
                time.sleep(0.3)

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, f"{os.getpid()}\n".encode())
        return fd, lock_file
    except BlockingIOError:
        print(
            f"mtk: error: could not acquire singleton lock {lock_name!r} after {max_retries} termination attempts.",
            file=sys.stderr,
        )
        os.close(fd)
        sys.exit(1)


def find_cpulimit_bin() -> str | None:
    runner_dir = Path(__file__).resolve().parent
    candidates = [
        str(runner_dir / "mtk-cpulimit"),
        str(runner_dir.parent / "vendor/cpulimit/src/cpulimit"),
        shutil.which("cpulimit"),
        "/opt/homebrew/bin/cpulimit",
        "/usr/local/bin/cpulimit",
    ]
    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MTK resource governor runner",
        add_help=False,
    )
    parser.add_argument("--time-limit", type=str, default=None)
    parser.add_argument("--memory-limit", type=str, default=None)
    parser.add_argument("--cpu-limit", type=str, default=None)
    parser.add_argument("--exclude-children", action="store_true")
    parser.add_argument("--singleton", nargs="?", const="", default=None)
    parser.add_argument("--singleton-wait", nargs="?", const="", default=None)
    parser.add_argument("command", nargs=argparse.REMAINDER)

    args = parser.parse_args()

    cmd = args.command
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]

    if not cmd:
        print("mtk: missing command to run under resource governor", file=sys.stderr)
        sys.exit(2)

    try:
        time_limit_sec = parse_duration(args.time_limit) if args.time_limit else None
        mem_limit_bytes = parse_bytes(args.memory_limit) if args.memory_limit else None
        cpu_limit_pct = parse_cpu(args.cpu_limit) if args.cpu_limit else None
    except ValueError as exc:
        parser.error(str(exc))
    max_cpu = 100 * (os.cpu_count() or 1)
    if cpu_limit_pct and cpu_limit_pct > max_cpu:
        parser.error(f"--cpu-limit must not exceed {max_cpu}% on this host")

    lock_fd = None
    lock_file = None
    if args.singleton is not None or args.singleton_wait is not None:
        wait_mode = args.singleton_wait is not None
        given_name = args.singleton_wait if wait_mode else args.singleton
        if not given_name:
            cmd_key = " ".join(cmd)
            given_name = hashlib.sha256(cmd_key.encode()).hexdigest()[:16]
        else:
            given_name = re.sub(r"[^\w\-.]", "_", given_name)
        lock_fd, lock_file = handle_singleton(given_name, wait_mode)

    cpulimit_proc = None
    cpulimit_bin = find_cpulimit_bin() if cpu_limit_pct else None
    if cpu_limit_pct and not cpulimit_bin:
        print(
            f"mtk: error: cpulimit executable not found; CPU limit ({cpu_limit_pct}%) cannot be enforced.",
            file=sys.stderr,
        )
        if lock_fd is not None:
            os.close(lock_fd)
        sys.exit(127)

    interactive = sys.stdin.isatty()
    foreground = os.tcgetpgrp(0) if interactive else None

    def set_foreground(group):
        previous = signal.signal(signal.SIGTTOU, signal.SIG_IGN)
        try:
            os.tcsetpgrp(0, group)
        finally:
            signal.signal(signal.SIGTTOU, previous)

    try:
        child = subprocess.Popen(cmd, start_new_session=not interactive,
                                 process_group=0 if interactive else None)
        if interactive:
            set_foreground(child.pid)
    except Exception as e:
        print(f"mtk: failed to execute {cmd[0]!r}: {e}", file=sys.stderr)
        if lock_fd is not None:
            os.close(lock_fd)
        sys.exit(127)

    tracked_pids = {child.pid}
    exit_reason = None

    def refresh_descendants():
        for pid in tuple(tracked_pids):
            tracked_pids.update(get_process_tree_pids(pid))

    def signal_workload(sig):
        # The group covers children spawned between samples; tracked PIDs cover
        # descendants that detached or were reparented after the root exited.
        try:
            os.killpg(child.pid, sig)
        except (ProcessLookupError, PermissionError):
            pass
        for pid in reversed(sorted(tracked_pids)):
            try:
                os.kill(pid, sig)
            except (ProcessLookupError, PermissionError):
                pass

    def stop_workload():
        refresh_descendants()
        signal_workload(signal.SIGTERM)
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            refresh_descendants()
            time.sleep(0.05)
        # Always finish escalation, even if TERM already reaped the root.
        signal_workload(signal.SIGKILL)
        child.wait()

    def forward_signal(sig, frame):
        nonlocal exit_reason
        if exit_reason is None:
            exit_reason = 128 + sig

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, forward_signal)
    signal.signal(signal.SIGWINCH, lambda sig, frame: signal_workload(sig))

    if cpu_limit_pct:
        cpu_args = [cpulimit_bin, "-l", str(cpu_limit_pct), "-p", str(child.pid)]
        if not args.exclude_children:
            cpu_args.append("-i")
        try:
            cpulimit_proc = subprocess.Popen(
                cpu_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except OSError as e:
            print(f"mtk: failed to start cpulimit: {e}", file=sys.stderr)
            exit_reason = 127

    started = time.monotonic()
    next_memory_check = started
    try:
        while child.poll() is None and exit_reason is None:
            refresh_descendants()
            now = time.monotonic()
            if cpulimit_proc and cpulimit_proc.poll() is not None and child.poll() is None:
                print(f"mtk: CPU limiter exited ({cpulimit_proc.returncode}); terminating workload", file=sys.stderr)
                exit_reason = 127
                break
            if mem_limit_bytes is not None and now >= next_memory_check:
                rss = get_process_tree_rss(child.pid)
                next_memory_check = now + 0.5
                if rss > mem_limit_bytes:
                    print(
                        f"\nmtk: memory limit exceeded ({rss / 1024**2:.1f} MiB > {mem_limit_bytes / 1024**2:.1f} MiB). Terminating...",
                        file=sys.stderr,
                    )
                    exit_reason = 137
            if exit_reason is None and time_limit_sec is not None and now - started >= time_limit_sec:
                print(f"\nmtk: time limit exceeded ({args.time_limit}). Terminating...", file=sys.stderr)
                exit_reason = 124
            if exit_reason is None:
                time.sleep(0.05)
        if exit_reason is not None:
            stop_workload()
        exit_code = child.wait()
    finally:
        if foreground is not None:
            set_foreground(foreground)
        if cpulimit_proc:
            try:
                cpulimit_proc.terminate()
                cpulimit_proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                cpulimit_proc.kill()
                cpulimit_proc.wait()
            # cpulimit may leave its target stopped when interrupted.
            signal_workload(signal.SIGCONT)
        if lock_fd is not None:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

    if exit_reason is not None:
        sys.exit(exit_reason)
    sys.exit(128 - exit_code if exit_code < 0 else exit_code)


if __name__ == "__main__":
    main()
