"""
Central configuration: environment variables, on-disk paths, and file-type
constants shared across the app.
"""

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

# Process-local locks (one per gunicorn worker) guarding read-modify-write of
# the small JSON files above.
cache_job_lock = threading.Lock()
gps_index_lock = threading.Lock()
users_lock = threading.Lock()
favorites_lock = threading.Lock()

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".heic", ".heif"}
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
