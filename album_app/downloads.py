"""
Download routes: a single original file, or a zip of a leaf album, a whole
album tree (recursively), or the favorites list.
"""

import os
import tempfile
import zipfile
from pathlib import Path

from flask import Blueprint, abort, after_this_request, request, send_file

from . import config
from .favorites import load_favorites
from .media import is_media, rel, safe_resolve

bp = Blueprint("downloads", __name__)


@bp.route("/api/download/photo")
def download_photo():
    """Sends the original file as-is (never the display-converted JPEG used
    for HEIC in the viewer), so downloads always keep full quality and
    metadata."""
    rel_path = request.args.get("path", "")
    abs_path = safe_resolve(rel_path)

    if not abs_path.is_file() or not is_media(abs_path):
        abort(404)

    return send_file(abs_path, as_attachment=True, download_name=abs_path.name)


def collect_files_for_zip(rel_path: str) -> list:
    """Gathers every photo/video file that belongs to the given path, for
    zip download: the favorites list, a single leaf album's items, or an
    album (and all its sub-albums) recursively."""
    if rel_path == config.FAVORITES_PATH:
        favs = load_favorites()
        return [config.PHOTOS_ROOT / p for p in sorted(favs) if (config.PHOTOS_ROOT / p).is_file()]

    abs_path = safe_resolve(rel_path)
    if abs_path.is_file():
        return [abs_path] if is_media(abs_path) else []

    return sorted(p for p in abs_path.rglob("*") if p.is_file() and is_media(p))


@bp.route("/api/download/zip")
def download_zip():
    rel_path = request.args.get("path", "")
    files = collect_files_for_zip(rel_path)

    if not files:
        abort(404, "Geen foto's gevonden om te downloaden")
    if len(files) > config.MAX_ZIP_FILES:
        abort(413, f"Te veel foto's in \u00e9\u00e9n keer ({len(files)}) — download een kleinere (sub)map.")

    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False, dir=str(config.CACHE_DIR))
    tmp.close()

    # ZIP_STORED (no re-compression): photos are already compressed formats
    # like JPEG, so trying to compress them further just burns CPU for
    # essentially zero size benefit.
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_STORED) as zf:
        for f in files:
            # Preserve the folder structure inside the zip (also avoids
            # filename collisions between e.g. two different "IMG_0001.jpg").
            zf.write(f, arcname=rel(f))

    @after_this_request
    def cleanup(response):
        try:
            os.remove(tmp.name)
        except Exception:
            pass
        return response

    if rel_path == config.FAVORITES_PATH:
        zip_name = "favorieten.zip"
    else:
        zip_name = f"{Path(rel_path).name or 'album'}.zip"

    return send_file(tmp.name, as_attachment=True, download_name=zip_name, mimetype="application/zip")
