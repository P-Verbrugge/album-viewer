"""
Pure EXIF-reading and formatting helpers. Used by media.py (to build the GPS
index while generating thumbnails) and exif_routes.py (to show camera info
in the viewer's info panel).
"""

from PIL import ExifTags
from PIL.ExifTags import GPSTAGS, TAGS


def dms_to_decimal(dms, ref):
    try:
        degrees, minutes, seconds = [float(x) for x in dms]
    except Exception:
        return None
    decimal = degrees + minutes / 60 + seconds / 3600
    if ref in ("S", "W"):
        decimal = -decimal
    return decimal


def format_exposure(value):
    try:
        f = float(value)
    except Exception:
        return None
    if f <= 0:
        return None
    if f < 1:
        return f"1/{round(1 / f)}s"
    return f"{f:.1f}s"


def format_fnumber(value):
    try:
        return f"f/{float(value):.1f}"
    except Exception:
        return None


def format_focal_length(value):
    try:
        return f"{float(value):.0f}mm"
    except Exception:
        return None


def read_exif(img):
    """Returns (dict of readable EXIF tags, gps dict or None)."""
    exif = img.getexif()
    if not exif:
        return {}, None

    data = {TAGS.get(tag_id, tag_id): value for tag_id, value in exif.items()}

    try:
        exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
        data.update({TAGS.get(tag_id, tag_id): value for tag_id, value in exif_ifd.items()})
    except Exception:
        pass

    gps_info = None
    try:
        gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
        if gps_ifd:
            gps_data = {GPSTAGS.get(tag_id, tag_id): value for tag_id, value in gps_ifd.items()}
            if "GPSLatitude" in gps_data and "GPSLongitude" in gps_data:
                lat = dms_to_decimal(gps_data["GPSLatitude"], gps_data.get("GPSLatitudeRef", "N"))
                lon = dms_to_decimal(gps_data["GPSLongitude"], gps_data.get("GPSLongitudeRef", "E"))
                if lat is not None and lon is not None:
                    gps_info = {"lat": lat, "lon": lon}
    except Exception:
        pass

    return data, gps_info
