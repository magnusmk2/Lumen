"""Read/write the shared configuration (~/.config/huectl/config.json)."""

import os
import json
import fcntl
import tempfile
import threading
from contextlib import contextmanager

CONFIG_PATH = os.path.expanduser("~/.config/huectl/config.json")
APP_NAME = "huectl#hyprland"
_LOCK = threading.RLock()


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def update_config(update):
    """Serialize read/modify/write across threads and processes; replace atomically."""
    directory = os.path.dirname(CONFIG_PATH)
    os.makedirs(directory, exist_ok=True)
    with _LOCK:
        lockfd = os.open(CONFIG_PATH + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(lockfd, "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            existing = load_config()
            if not isinstance(existing, dict):
                raise ValueError("Invalid configuration")
            result = update(existing)
            fd, path = tempfile.mkstemp(prefix=".huectl-", dir=directory)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(existing, f, indent=2, ensure_ascii=False, allow_nan=False)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(path, CONFIG_PATH)
            finally:
                if os.path.exists(path):
                    os.unlink(path)
            return result


def save_config(cfg):
    """Merge top-level keys without losing unrelated concurrent updates."""
    return update_config(lambda existing: existing.update(cfg))


@contextmanager
def stream_lock():
    """One GUI, CLI or identify session for this configuration at a time."""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    fd = os.open(CONFIG_PATH + ".stream.lock", os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(fd, "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise RuntimeError("Another Lumen session is already streaming") from e
        yield
