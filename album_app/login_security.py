"""
Login rate-limiting (to slow down password guessing) and the file-triggered
password-reset mechanism (since this self-hosted app has no email server to
send a reset link to).
"""

import json
import time

from . import config


# --------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------

def _load_attempts() -> dict:
    try:
        return json.loads(config.LOGIN_ATTEMPTS_FILE.read_text())
    except Exception:
        return {}


def _save_attempts_unlocked(data: dict) -> None:
    config.LOGIN_ATTEMPTS_FILE.write_text(json.dumps(data))


def _recent_attempts(entry: list, now: float) -> list:
    return [t for t in entry if now - t < config.LOGIN_ATTEMPT_WINDOW_SECONDS]


def seconds_until_unlocked(username: str) -> int:
    """Returns how many seconds until this username may try to log in
    again, or 0 if it isn't currently locked out."""
    if not username:
        return 0
    now = time.time()
    data = _load_attempts()
    recent = _recent_attempts(data.get(username, []), now)
    if len(recent) < config.MAX_LOGIN_ATTEMPTS:
        return 0
    unlock_at = max(recent) + config.LOGIN_LOCKOUT_SECONDS
    return max(0, int(unlock_at - now))


def register_failed_attempt(username: str) -> None:
    if not username:
        return
    with config.locked_file(config.LOGIN_ATTEMPTS_LOCK_FILE):
        now = time.time()
        data = _load_attempts()
        entry = _recent_attempts(data.get(username, []), now)
        entry.append(now)
        data[username] = entry
        _save_attempts_unlocked(data)


def clear_attempts(username: str) -> None:
    if not username:
        return
    with config.locked_file(config.LOGIN_ATTEMPTS_LOCK_FILE):
        data = _load_attempts()
        if username in data:
            del data[username]
            _save_attempts_unlocked(data)


# --------------------------------------------------------------------------
# File-triggered password reset
# --------------------------------------------------------------------------

def reset_trigger_active() -> bool:
    """True if someone with real filesystem/docker access to the server has
    recently created the trigger file, and it hasn't expired yet."""
    if not config.RESET_TRIGGER_FILE.exists():
        return False
    age = time.time() - config.RESET_TRIGGER_FILE.stat().st_mtime
    if age > config.RESET_TRIGGER_MAX_AGE_SECONDS:
        config.RESET_TRIGGER_FILE.unlink(missing_ok=True)
        return False
    return True


def consume_reset_trigger() -> None:
    """One-time use: once a reset has actually been performed, the trigger
    is gone, so someone can't keep resetting passwords with a single
    `docker exec` command."""
    config.RESET_TRIGGER_FILE.unlink(missing_ok=True)
