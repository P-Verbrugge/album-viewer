"""
The main folder-browsing route: shows subfolders as albums, or the photos
and videos inside a leaf folder — with pagination so huge folders don't get
sent (or rendered) all in one go.
"""

from flask import Blueprint, abort, jsonify, request, session

from . import config
from .favorites import load_favorites
from .media import find_cover, is_media, is_video, rel, safe_resolve

bp = Blueprint("browse", __name__)


def paginate(items: list, offset: int, limit: int):
    total = len(items)
    page = items[offset : offset + limit]
    has_more = offset + limit < total
    return page, total, has_more


@bp.route("/api/browse")
def browse():
    rel_path = request.args.get("path", "")
    favs = load_favorites(session.get("username"))

    offset = max(0, request.args.get("offset", default=0, type=int) or 0)
    limit = request.args.get("limit", default=config.DEFAULT_PAGE_SIZE, type=int) or config.DEFAULT_PAGE_SIZE
    limit = max(1, min(limit, config.MAX_PAGE_SIZE))

    if rel_path == config.FAVORITES_PATH:
        all_favs = sorted(favs)
        page_favs, total, has_more = paginate(all_favs, offset, limit)
        items = []
        for fav_path in page_favs:
            abs_p = config.PHOTOS_ROOT / fav_path
            if abs_p.is_file() and is_media(abs_p):
                items.append(
                    {
                        "name": abs_p.name,
                        "path": fav_path,
                        "favorite": True,
                        "kind": "video" if is_video(abs_p) else "photo",
                    }
                )
        breadcrumbs = [{"name": "Favorieten", "path": config.FAVORITES_PATH}]
        return jsonify(
            {
                "type": "photos",
                "path": config.FAVORITES_PATH,
                "breadcrumbs": breadcrumbs,
                "items": items,
                "total": total,
                "offset": offset,
                "has_more": has_more,
            }
        )

    abs_path = safe_resolve(rel_path)

    if not abs_path.is_dir():
        abort(400, "Pad is geen map")

    try:
        entries = sorted(abs_path.iterdir(), key=lambda p: p.name.lower())
    except PermissionError:
        abort(403)

    subdirs = [p for p in entries if p.is_dir() and not p.name.startswith(".")]
    media_files = [p for p in entries if p.is_file() and is_media(p)]

    breadcrumbs = []
    if rel_path.strip("/"):
        parts = rel_path.strip("/").split("/")
        for i, part in enumerate(parts):
            breadcrumbs.append({"name": part, "path": "/".join(parts[: i + 1])})

    if subdirs:
        # Only compute a cover photo (which involves a recursive folder search)
        # for the folders on this page — not for every subfolder up front.
        page_dirs, total, has_more = paginate(subdirs, offset, limit)
        items = []
        for d in page_dirs:
            cover = find_cover(d)
            items.append(
                {
                    "name": d.name,
                    "path": rel(d),
                    "cover": rel(cover) if cover else None,
                }
            )
        return jsonify(
            {
                "type": "folders",
                "path": rel_path.strip("/"),
                "breadcrumbs": breadcrumbs,
                "items": items,
                "total": total,
                "offset": offset,
                "has_more": has_more,
            }
        )

    if media_files:
        page_photos, total, has_more = paginate(media_files, offset, limit)
        items = [
            {
                "name": p.name,
                "path": rel(p),
                "favorite": rel(p) in favs,
                "kind": "video" if is_video(p) else "photo",
            }
            for p in page_photos
        ]
        return jsonify(
            {
                "type": "photos",
                "path": rel_path.strip("/"),
                "breadcrumbs": breadcrumbs,
                "items": items,
                "total": total,
                "offset": offset,
                "has_more": has_more,
            }
        )

    return jsonify(
        {
            "type": "empty",
            "path": rel_path.strip("/"),
            "breadcrumbs": breadcrumbs,
            "items": [],
            "total": 0,
            "offset": 0,
            "has_more": False,
        }
    )
