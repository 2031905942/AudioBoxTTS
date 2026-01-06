# This Python file uses the following encoding: utf-8
"""Development runner.

Watches source files and restarts the GUI process automatically.

Usage (Windows):
  音频工具箱.bat dev

Notes:
- This is intended for development only.
- It does not attempt in-process hot-reload; it restarts the Python process.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import psutil


@dataclass(frozen=True)
class WatchOptions:
    root: Path
    poll_interval_s: float
    debounce_s: float


def _iter_watch_files(root: Path) -> list[Path]:
    """Return files to watch.

    Keep this small and predictable: core entry + Source python files.
    """
    files: list[Path] = []

    main_py = root / "main.py"
    if main_py.is_file():
        files.append(main_py)

    source_dir = root / "Source"
    if source_dir.is_dir():
        files.extend(p for p in source_dir.rglob("*.py") if p.is_file())

    return files


def _snapshot_mtime(files: list[Path]) -> dict[str, float]:
    snapshot: dict[str, float] = {}
    for path in files:
        try:
            snapshot[str(path)] = path.stat().st_mtime
        except FileNotFoundError:
            snapshot[str(path)] = -1.0
    return snapshot


def _has_changes(prev: dict[str, float], current: dict[str, float]) -> bool:
    if prev.keys() != current.keys():
        return True
    for key, mtime in current.items():
        if prev.get(key) != mtime:
            return True
    return False


def _kill_process_tree(pid: int, timeout_s: float = 3.0) -> None:
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return

    children = proc.children(recursive=True)
    for child in children:
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            pass

    try:
        proc.terminate()
    except psutil.NoSuchProcess:
        return

    gone, alive = psutil.wait_procs(children + [proc], timeout=timeout_s)
    if alive:
        for p in alive:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass


def _start_child(python_exe: str, root: Path) -> subprocess.Popen:
    env = os.environ.copy()
    # Ensure relative imports / sys.path.append(".") behave as expected.
    cwd = str(root)

    # On Windows, this keeps console behavior consistent with the current terminal.
    return subprocess.Popen(
        [python_exe, "-B", "main.py"],
        cwd=cwd,
        env=env,
    )


def run_dev_runner(options: WatchOptions, python_exe: str) -> int:
    root = options.root

    print("[dev_runner] watching for changes under:", root)
    print("[dev_runner] python:", python_exe)

    watched_files = _iter_watch_files(root)
    if not watched_files:
        print("[dev_runner] no files found to watch; exiting")
        return 2

    prev_snapshot = _snapshot_mtime(watched_files)

    child = _start_child(python_exe, root)
    print(f"[dev_runner] started child pid={child.pid}")
    snapshot_at_start = prev_snapshot

    last_change_at: float | None = None

    try:
        while True:
            time.sleep(options.poll_interval_s)

            # Refresh watch list (handles new/removed files).
            watched_files = _iter_watch_files(root)
            current_snapshot = _snapshot_mtime(watched_files)

            changed = _has_changes(prev_snapshot, current_snapshot)
            if changed:
                prev_snapshot = current_snapshot
                last_change_at = time.time()

            # Debounce restarts to avoid restarting mid-save.
            if last_change_at is not None and (time.time() - last_change_at) >= options.debounce_s:
                last_change_at = None
                print("[dev_runner] change detected -> restarting")
                if child is not None:
                    _kill_process_tree(child.pid)
                child = _start_child(python_exe, root)
                snapshot_at_start = prev_snapshot
                print(f"[dev_runner] restarted child pid={child.pid}")

            # If the child exits (crash or normal close), do NOT auto-restart.
            # Wait for file changes to restart, otherwise we'd create a tight crash loop.
            if child is not None:
                exit_code = child.poll()
                if exit_code is not None:
                    print(f"[dev_runner] child exited with code {exit_code}; waiting for changes to restart")
                    child = None

            # If there's no running child, restart only after a change (debounced).
            if child is None and changed:
                # Mark time; debounce will handle the actual restart.
                if last_change_at is None:
                    last_change_at = time.time()

    except KeyboardInterrupt:
        print("\n[dev_runner] stopping...")
        if child is not None:
            _kill_process_tree(child.pid)
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="AudioBox dev runner (auto restart)")
    parser.add_argument(
        "--poll",
        type=float,
        default=0.5,
        help="Polling interval seconds (default: 0.5)",
    )
    parser.add_argument(
        "--debounce",
        type=float,
        default=0.8,
        help="Restart debounce seconds after last change (default: 0.8)",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    opts = WatchOptions(root=root, poll_interval_s=args.poll, debounce_s=args.debounce)

    # Use the same interpreter that runs the dev runner.
    python_exe = sys.executable
    return run_dev_runner(opts, python_exe)


if __name__ == "__main__":
    raise SystemExit(main())
