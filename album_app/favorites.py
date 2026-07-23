"""
Favorites: stored server-side, per account, so each person's favorites are
their own — but still survive across devices/browsers for that one account.
"""

import json

from flask import Blueprint, abort, jsonify, request, session

from . import config
from .media import is_media, rel, safe_resolve

bp = Blueprint("favorites", __name__)


def _load_all() -> dict:
    try:
        return json.loads(config.FAVORITES_FILE.read_text())
    except Exception:
        return {}


def _save_all(all_favs: dict) -> None:
    config.FAVORITES_FILE.write_text(json.dumps(all_favs))


def load_favorites(username: str) -> set:
    return set(_load_all().get(username, []))


def save_favorites(username: str, favs: set) -> None:
    with config.favorites_lock:
        all_favs = _load_all()
        all_favs[username] = sorted(favs)
        _save_all(all_favs)


def delete_user_favorites(username: str) -> None:
    with config.favorites_lock:
        all_favs = _load_all()
        if username in all_favs:
            del all_favs[username]
            _save_all(all_favs)


@bp.route("/api/favorites/toggle", methods=["POST"])
def toggle_favorite():
    username = session.get("username")
    body = request.get_json(force=True, silent=True) or {}
    abs_path = safe_resolve(body.get("path", ""))

    if not abs_path.is_file() or not is_media(abs_path):
        abort(404)

    normalized = rel(abs_path)
    favs = load_favorites(username)
    is_fav = normalized in favs
    if is_fav:
        favs.discard(normalized)
    else:
        favs.add(normalized)
    save_favorites(username, favs)

    return jsonify({"path": normalized, "favorite": not is_fav})
