"""The map overview route, backed by the GPS index built in media.py."""

from pathlib import Path

from flask import Blueprint, jsonify, session

from . import config
from .favorites import load_favorites
from .media import load_gps_index

bp = Blueprint("gps_map", __name__)


@bp.route("/api/map/photos")
def map_photos():
    """Returns every photo that has a known GPS location, for the map
    overview. Backed by the GPS index built up in ensure_thumbnail(), so
    this stays fast even for large libraries — no re-scanning of files here."""
    favs = load_favorites(session.get("username"))
    index = load_gps_index()

    items = []
    for rel_path, entry in index.items():
        lat, lon = entry.get("lat"), entry.get("lon")
        if lat is None or lon is None:
            continue
        if not (config.PHOTOS_ROOT / rel_path).is_file():
            continue  # photo was since deleted/moved; skip stale entries
        items.append(
            {
                "path": rel_path,
                "name": entry.get("name", Path(rel_path).name),
                "lat": lat,
                "lon": lon,
                "favorite": rel_path in favs,
            }
        )

    return jsonify({"items": items, "total": len(items)})
