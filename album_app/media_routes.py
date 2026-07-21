"""
Routes that serve actual image/video bytes: thumbnails, full-size photos
(with on-the-fly HEIC-to-JPEG conversion), and video streams.
"""

from flask import Blueprint, abort, request, send_file

from . import config
from .media import (
    HeicNotSupported,
    ensure_thumbnail,
    is_image,
    is_media,
    is_video,
    safe_resolve,
    serve_as_jpeg_path,
)

bp = Blueprint("media_routes", __name__)


@bp.route("/api/thumbnail")
def thumbnail():
    rel_path = request.args.get("path", "")
    size = int(request.args.get("size", config.DEFAULT_THUMB_SIZE))
    abs_path = safe_resolve(rel_path)

    if not abs_path.is_file() or not is_media(abs_path):
        abort(404)

    try:
        cache_file = ensure_thumbnail(abs_path, size)
    except Exception:
        abort(415, "Kan geen thumbnail maken van dit bestand")

    return send_file(cache_file, mimetype="image/jpeg")


@bp.route("/api/image")
def full_image():
    rel_path = request.args.get("path", "")
    abs_path = safe_resolve(rel_path)

    if not abs_path.is_file() or not is_image(abs_path):
        abort(404)

    if abs_path.suffix.lower() in config.HEIF_EXTS:
        try:
            cache_file = serve_as_jpeg_path(abs_path)
        except HeicNotSupported:
            abort(415, "HEIC wordt niet ondersteund — herbouw de container met pillow-heif")
        except Exception:
            abort(415, "Kan dit HEIC-bestand niet converteren")
        return send_file(cache_file, mimetype="image/jpeg")

    return send_file(abs_path)


@bp.route("/api/video")
def full_video():
    rel_path = request.args.get("path", "")
    abs_path = safe_resolve(rel_path)

    if not abs_path.is_file() or not is_video(abs_path):
        abort(404)

    mimetype = config.VIDEO_MIME_TYPES.get(abs_path.suffix.lower(), "application/octet-stream")
    # conditional=True (Flask's default) makes send_file honor Range
    # requests, which is what lets the browser seek/scrub through the video.
    return send_file(abs_path, mimetype=mimetype, conditional=True)
