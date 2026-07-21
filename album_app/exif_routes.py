"""The detailed per-photo EXIF info route used by the viewer's info panel."""

from flask import Blueprint, abort, jsonify, request
from PIL import Image

from .exif_utils import format_exposure, format_fnumber, format_focal_length, read_exif
from .media import is_image, safe_resolve

bp = Blueprint("exif_routes", __name__)


@bp.route("/api/exif")
def exif_info():
    rel_path = request.args.get("path", "")
    abs_path = safe_resolve(rel_path)

    if not abs_path.is_file() or not is_image(abs_path):
        abort(404)

    result = {
        "filename": abs_path.name,
        "size_bytes": abs_path.stat().st_size,
        "width": None,
        "height": None,
        "camera": None,
        "lens": None,
        "date_taken": None,
        "exposure": None,
        "fnumber": None,
        "iso": None,
        "focal_length": None,
        "gps": None,
    }

    try:
        with Image.open(abs_path) as img:
            result["width"], result["height"] = img.size
            data, gps = read_exif(img)
    except Exception:
        data, gps = {}, None

    def first(*names):
        for name in names:
            if data.get(name) not in (None, ""):
                return data[name]
        return None

    make = first("Make")
    model = first("Model")
    camera_parts = [str(p).strip() for p in (make, model) if p]
    result["camera"] = " ".join(camera_parts) if camera_parts else None

    lens = first("LensModel")
    result["lens"] = str(lens) if lens else None

    date_taken = first("DateTimeOriginal", "DateTime")
    result["date_taken"] = str(date_taken) if date_taken else None

    exposure = first("ExposureTime")
    result["exposure"] = format_exposure(exposure) if exposure is not None else None

    fnumber = first("FNumber")
    result["fnumber"] = format_fnumber(fnumber) if fnumber is not None else None

    iso = first("ISOSpeedRatings", "PhotographicSensitivity")
    try:
        result["iso"] = int(iso) if iso is not None else None
    except Exception:
        result["iso"] = None

    focal = first("FocalLength")
    result["focal_length"] = format_focal_length(focal) if focal is not None else None

    result["gps"] = gps

    return jsonify(result)
