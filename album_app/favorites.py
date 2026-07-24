"""
Favorites: stored server-side (shared, not per-browser), so they apply to
everyone visiting the app, regardless of browser/device.
"""

import json

from flask import Blueprint, abort, jsonify, request

from . import config
from .media import is_media, rel, safe_resolve

bp = Blueprint("favorites", __name__)


def load_favorites() -> set:
    try:
        data = json.loads(config.FAVORITES_FILE.read_text())
    except Exception:
        return set()

    if isinstance(data, list):
        return set(data)

    if isinstance(data, dict):
        # Briefly, this app stored favorites per-account. Merge everyone's
        # favorites back into one shared set rather than losing any.
        merged = set()
        for favs in data.values():
            merged.update(favs)
        return merged

    return set()


def save_favorites(favs: set) -> None:
    config.FAVORITES_FILE.write_text(json.dumps(sorted(favs)))


@bp.route("/api/favorites/toggle", methods=["POST"])
def toggle_favorite():
    body = request.get_json(force=True, silent=True) or {}
    abs_path = safe_resolve(body.get("path", ""))

    if not abs_path.is_file() or not is_media(abs_path):
        abort(404)

    normalized = rel(abs_path)
    favs = load_favorites()
    is_fav = normalized in favs
    if is_fav:
        favs.discard(normalized)
    else:
        favs.add(normalized)
    save_favorites(favs)

    return jsonify({"path": normalized, "favorite": not is_fav})
