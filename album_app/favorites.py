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
        data = json.loads(config.FAVORITES_FILE.read_text())
    except Exception:
        return {}

    if isinstance(data, dict):
        return data

    if isinstance(data, list):
        # Pre-multi-user installations stored favorites as one flat, shared
        # list. Rather than crash on the format mismatch (or silently lose
        # them), migrate them once to the first admin account, and persist
        # that so this only ever happens a single time.
        from .auth import load_users

        users = load_users()
        admin_username = next(
            (username for username, info in sorted(users.items()) if info.get("is_admin")),
            None,
        )
        migrated = {admin_username: data} if admin_username else {}
        _save_all(migrated)
        return migrated

    return {}


def _save_all(all_favs: dict) -> None:
    config.FAVORITES_FILE.write_text(json.dumps(all_favs))


def load_favorites(username: str) -> set:
    return set(_load_all().get(username, []))


def save_favorites(username: str, favs: set) -> None:
    with config.locked_file(config.FAVORITES_LOCK_FILE):
        all_favs = _load_all()
        all_favs[username] = sorted(favs)
        _save_all(all_favs)


def delete_user_favorites(username: str) -> None:
    with config.locked_file(config.FAVORITES_LOCK_FILE):
        all_favs = _load_all()
        if username in all_favs:
            del all_favs[username]
            _save_all(all_favs)


def toggle_favorite_for_user(username: str, path: str) -> bool:
    """Atomically toggles one path in one user's favorites — load, modify,
    and save all under a single lock acquisition — so two rapid toggles for
    the same account (e.g. clicking two hearts in quick succession) can't
    silently clobber each other the way separate load-then-save calls could.
    Returns the new state (True = now a favorite)."""
    with config.locked_file(config.FAVORITES_LOCK_FILE):
        all_favs = _load_all()
        favs = set(all_favs.get(username, []))
        is_fav = path in favs
        if is_fav:
            favs.discard(path)
        else:
            favs.add(path)
        all_favs[username] = sorted(favs)
        _save_all(all_favs)
        return not is_fav


@bp.route("/api/favorites/toggle", methods=["POST"])
def toggle_favorite():
    username = session.get("username")
    body = request.get_json(force=True, silent=True) or {}
    abs_path = safe_resolve(body.get("path", ""))

    if not abs_path.is_file() or not is_media(abs_path):
        abort(404)

    normalized = rel(abs_path)
    is_favorite_now = toggle_favorite_for_user(username, normalized)

    return jsonify({"path": normalized, "favorite": is_favorite_now})
