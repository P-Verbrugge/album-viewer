"""
Everything related to locating and processing media files on disk: path
safety, image/video type checks, album cover lookup, the GPS index, and
thumbnail generation (including HEIC-to-JPEG and video-frame extraction).
"""

import hashlib
import json
import subprocess
from pathlib import Path

from flask import abort
from PIL import Image, ImageOps

from . import config
from .exif_utils import read_exif


# --------------------------------------------------------------------------
# Path helpers
# --------------------------------------------------------------------------

def safe_resolve(rel_path: str) -> Path:
    """Turns a relative path (from the client) into an absolute path, and
    blocks anything that falls outside PHOTOS_ROOT (path traversal)."""
    rel_path = (rel_path or "").strip("/")
    candidate = (config.PHOTOS_ROOT / rel_path).resolve()
    if candidate != config.PHOTOS_ROOT and config.PHOTOS_ROOT not in candidate.parents:
        abort(403)
    if not candidate.exists():
        abort(404)
    return candidate


def rel(path: Path) -> str:
    return str(path.relative_to(config.PHOTOS_ROOT).as_posix())


# --------------------------------------------------------------------------
# File-type checks
# --------------------------------------------------------------------------

def is_image(path: Path) -> bool:
    return path.suffix.lower() in config.IMAGE_EXTS and not path.name.startswith(".")


def is_video(path: Path) -> bool:
    return path.suffix.lower() in config.VIDEO_EXTS and not path.name.startswith(".")


def is_media(path: Path) -> bool:
    return is_image(path) or is_video(path)


def find_cover(dir_path: Path, max_depth: int = config.COVER_SEARCH_DEPTH):
    """Finds the first photo or video (alphabetically, shallowest first)
    under dir_path, so an album tile can show a preview thumbnail."""
    try:
        entries = sorted(dir_path.iterdir(), key=lambda p: p.name.lower())
    except PermissionError:
        return None

    files = [p for p in entries if p.is_file() and is_media(p)]
    if files:
        return files[0]

    if max_depth <= 0:
        return None

    for sub in [p for p in entries if p.is_dir() and not p.name.startswith(".")]:
        cover = find_cover(sub, max_depth - 1)
        if cover:
            return cover
    return None


# --------------------------------------------------------------------------
# GPS index (built up opportunistically while generating thumbnails, used by
# the map overview so it never needs a separate full-library scan)
# --------------------------------------------------------------------------

def load_gps_index() -> dict:
    try:
        return json.loads(config.GPS_INDEX_FILE.read_text())
    except Exception:
        return {}


def save_gps_index(index: dict) -> None:
    config.GPS_INDEX_FILE.write_text(json.dumps(index))


def record_gps(rel_path: str, name: str, mtime: int, gps) -> None:
    with config.gps_index_lock:
        index = load_gps_index()
        index[rel_path] = {
            "mtime": mtime,
            "name": name,
            "lat": gps["lat"] if gps else None,
            "lon": gps["lon"] if gps else None,
        }
        save_gps_index(index)


# --------------------------------------------------------------------------
# Thumbnail generation
# --------------------------------------------------------------------------

def generate_video_thumbnail(abs_path: Path, out_path: Path, size: int) -> None:
    """Extracts a still frame from a video with ffmpeg to use as its
    thumbnail. Tries a frame 1 second in first (usually avoids a black
    opening frame); for very short clips that fails, so it falls back to
    the very first frame."""
    for seek in ("00:00:01", "00:00:00"):
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", seek,
                "-i", str(abs_path),
                "-frames:v", "1",
                "-vf", f"scale='min({size},iw)':-2",
                str(out_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        if out_path.exists() and out_path.stat().st_size > 0:
            return
    raise RuntimeError(f"ffmpeg could not extract a thumbnail frame from {abs_path}")


def ensure_thumbnail(abs_path: Path, size: int) -> Path:
    """Generates (if needed) a thumbnail and returns the cache file.
    Used by both the /api/thumbnail route and the bulk-cache job.

    While the file is open anyway, this also opportunistically checks
    whether its GPS location has been recorded yet in the GPS index (used
    by the map overview), so browsing/caching photos gradually builds up
    the map data without a separate full-library scan. Videos don't carry
    GPS the same way, so that check is skipped for them."""
    mtime = int(abs_path.stat().st_mtime)
    cache_key = hashlib.sha1(f"{abs_path}:{mtime}:{size}".encode()).hexdigest()
    cache_file = config.CACHE_DIR / f"{cache_key}.jpg"

    if is_video(abs_path):
        if not cache_file.exists():
            generate_video_thumbnail(abs_path, cache_file, size)
        return cache_file

    normalized = rel(abs_path)
    gps_entry = load_gps_index().get(normalized)
    needs_gps_check = gps_entry is None or gps_entry.get("mtime") != mtime
    needs_thumb = not cache_file.exists()

    if needs_thumb or needs_gps_check:
        with Image.open(abs_path) as img:
            if needs_gps_check:
                _, gps = read_exif(img)
                record_gps(normalized, abs_path.name, mtime, gps)

            if needs_thumb:
                thumb_img = ImageOps.exif_transpose(img)  # respect rotation from EXIF
                thumb_img = thumb_img.convert("RGB")
                thumb_img.thumbnail((size, size))
                thumb_img.save(cache_file, "JPEG", quality=85)

    return cache_file


class HeicNotSupported(Exception):
    """Raised when a HEIC/HEIF file needs converting but pillow-heif isn't
    available in this build."""


def serve_as_jpeg_path(abs_path: Path) -> Path:
    """Converts HEIC/HEIF to JPEG (browsers can't display HEIC directly) and
    returns the cached result, generating it first if needed. Raises
    HeicNotSupported if the plugin isn't available, or lets a PIL error
    propagate if the conversion itself fails; the caller (a route) turns
    either into a proper HTTP error."""
    if not config.HEIC_SUPPORTED:
        raise HeicNotSupported()

    mtime = int(abs_path.stat().st_mtime)
    cache_key = hashlib.sha1(f"{abs_path}:{mtime}:full-jpeg".encode()).hexdigest()
    cache_file = config.CACHE_DIR / f"{cache_key}_full.jpg"

    if not cache_file.exists():
        with Image.open(abs_path) as img:
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")
            img.save(cache_file, "JPEG", quality=92)

    return cache_file
