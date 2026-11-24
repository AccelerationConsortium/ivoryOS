"""Refuse to serve one deck script from two processes at once.

Each deck script gets a lock file, keyed on the script's path, in the system temp folder. The
process serving the script holds an OS lock on it for as long as it runs, so the lock goes away
by itself when that process exits or is killed: a crash never leaves a stale lock behind. Beside
it, a small JSON file says which process holds it, so a second copy can say what to stop.
"""
import hashlib
import json
import os
import tempfile
import time

LOCK_DIR = os.path.join(tempfile.gettempdir(), "ivoryos-locks")

_held = {}  # script path -> open lock file, kept open for the life of the process


class AlreadyRunning(RuntimeError):
    """Another process is already serving this deck script."""

    def __init__(self, script: str, holder: dict):
        self.script = script
        self.holder = holder
        super().__init__(_already_running_message(script, holder))


def _script_key(script: str) -> str:
    return os.path.normcase(os.path.realpath(script))


def _lock_paths(script: str):
    digest = hashlib.sha1(_script_key(script).encode("utf-8")).hexdigest()[:16]
    base = os.path.join(LOCK_DIR, f"{os.path.splitext(os.path.basename(script))[0]}-{digest}")
    return base + ".lock", base + ".json"


def _try_lock(handle) -> bool:
    """Take an exclusive lock on the open file ``handle`` without waiting; False if it is taken."""
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _read_holder(info_path: str) -> dict:
    try:
        with open(info_path, encoding="utf-8") as f:
            holder = json.load(f)
        return holder if isinstance(holder, dict) else {}
    except (OSError, ValueError):
        return {}


def _already_running_message(script: str, holder: dict) -> str:
    pid = holder.get("pid")
    details = [f"process {pid}" if pid else None, holder.get("url"),
               f"started {holder['started']}" if holder.get("started") else None]
    details = ", ".join(d for d in details if d)
    if pid:
        kill = f"taskkill /PID {pid} /F" if os.name == "nt" else f"kill {pid}"
        how = f"press Ctrl+C in its terminal, or run `{kill}`"
    else:
        how = "press Ctrl+C in its terminal, or end its Python process"
    return (
        f"ivoryOS is already running {os.path.basename(script)}" + (f" ({details})" if details else "") + ".\n"
        f"Only one copy of a deck script can control its instruments. "
        f"Stop the running one first ({how}), then start this one again.\n"
        f"Script: {_script_key(script)}"
    )


def acquire(script: str, **info) -> None:
    """
    Claim ``script`` for this process until it exits.
    :param script: path of the deck script
    :param info: what a second copy should be told about this one, such as ``url``
    :raises AlreadyRunning: another live process holds the script
    """
    key = _script_key(script)
    if key in _held:
        return
    os.makedirs(LOCK_DIR, exist_ok=True)
    lock_path, info_path = _lock_paths(script)
    handle = open(lock_path, "a+")
    if not _try_lock(handle):
        handle.close()
        raise AlreadyRunning(script, _read_holder(info_path))
    _held[key] = handle
    holder = dict(info, pid=os.getpid(), started=time.strftime("%Y-%m-%d %H:%M:%S"), script=key)
    try:
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(holder, f)
    except OSError:
        pass  # the lock still holds; a second copy just can't say which process has it


def release(script: str) -> None:
    """Give up the claim on ``script`` (it is given up anyway when the process exits)."""
    handle = _held.pop(_script_key(script), None)
    if handle is None:
        return
    try:
        os.remove(_lock_paths(script)[1])
    except OSError:
        pass
    handle.close()
