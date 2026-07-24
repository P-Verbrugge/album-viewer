"""
Central configuration: environment variables, on-disk paths, and file-type
constants shared across the app.
"""

import contextlib
import fcntl
import os
import threading
from pathlib import Path

PHOTOS_ROOT = Path(os.environ.get("PHOTOS_ROOT", "/photos")).resolve()
CACHE_DIR = Path(os.environ.get("CACHE_DIR", "/cache")).resolve()
DEFAULT_THUMB_SIZE = int(os.environ.get("THUMB_SIZE", "400"))
COVER_SEARCH_DEPTH = 3  # how deep we search for a cover photo for an album tile

# App-data files, all living in CACHE_DIR so they persist in the same Docker
# volume as the thumbnail cache.
FAVORITES_FILE = CACHE_DIR / "favorites.json"
CACHE_JOB_FILE = CACHE_DIR / "cache_job.json"
GPS_INDEX_FILE = CACHE_DIR / "gps_index.json"
USERS_FILE = CACHE_DIR / "users.json"
ACCOUNT_FILE = CACHE_DIR / "account.json"  # legacy single-account file, kept only for migration
SECRET_KEY_FILE = CACHE_DIR / "secret_key.txt"

FAVORITES_PATH = "__favorites__"  # virtual path for the favorites overview

# Process-local locks (kept for in-process callers that don't need the
# cross-process guarantee below).
cache_job_lock = threading.Lock()
gps_index_lock = threading.Lock()
users_lock = threading.Lock()
favorites_lock = threading.Lock()

# gunicorn runs multiple *worker processes*, each with its own separate
# Python memory (and therefore its own separate threading.Lock instances
# above) — a plain in-process lock does nothing to stop two different
# worker processes from both reading users.json, both modifying their own
# in-memory copy, and one overwriting the other's change when they save.
# fcntl.flock operates at the OS level on the file itself, so it correctly
# serializes access across *both* threads and separate processes.
USERS_LOCK_FILE = CACHE_DIR / "users.json.lock"
FAVORITES_LOCK_FILE = CACHE_DIR / "favorites.json.lock"
GPS_INDEX_LOCK_FILE = CACHE_DIR / "gps_index.json.lock"


@contextlib.contextmanager
def locked_file(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)

RAW_EXTS = {".cr2", ".cr3", ".nef", ".nrw", ".arw", ".rw2", ".orf", ".raf", ".pef", ".srw", ".dng"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".heic", ".heif"} | RAW_EXTS
HEIF_EXTS = {".heic", ".heif"}  # no browser can display these formats directly
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".webm"}
VIDEO_MIME_TYPES = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".webm": "video/webm",
}

DEFAULT_PAGE_SIZE = 300
MAX_PAGE_SIZE = 1000
MAX_ZIP_FILES = 3000  # sanity limit so one request can't hang the server for hours

# Login rate-limiting: after MAX_LOGIN_ATTEMPTS failures for a given username
# within LOGIN_ATTEMPT_WINDOW_SECONDS, that username is locked out for
# LOGIN_LOCKOUT_SECONDS. Tracked per-username (not per-IP), which is the
# relevant threat model for a small home app: slowing down someone guessing
# a specific person's password.
LOGIN_ATTEMPTS_FILE = CACHE_DIR / "login_attempts.json"
LOGIN_ATTEMPTS_LOCK_FILE = CACHE_DIR / "login_attempts.json.lock"
MAX_LOGIN_ATTEMPTS = 5
LOGIN_ATTEMPT_WINDOW_SECONDS = 5 * 60
LOGIN_LOCKOUT_SECONDS = 5 * 60

# File-triggered password reset: since this self-hosted app has no email
# server to send a reset link to, "proof of legitimate access" instead means
# creating this file via `docker exec` — something only someone who can
# already reach the server's shell can do. It's a one-time trigger that also
# expires on its own if nobody uses it.
RESET_TRIGGER_FILE = CACHE_DIR / "allow_password_reset"
RESET_TRIGGER_MAX_AGE_SECONDS = 10 * 60

CACHE_DIR.mkdir(parents=True, exist_ok=True)

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIC_SUPPORTED = True
except ImportError:
    # The container hasn't been rebuilt with pillow-heif in requirements.txt yet,
    # or no wheel is available for this platform. HEIC files are simply skipped
    # instead of crashing the app.
    HEIC_SUPPORTED = False

try:
    import rawpy  # noqa: F401
    RAW_SUPPORTED = True
except ImportError:
    # Same idea as HEIC_SUPPORTED above, but for camera RAW formats.
    RAW_SUPPORTED = False
