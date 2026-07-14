"""
Simpele, zelfstandige albumviewer (geen Immich nodig).

Logica per map:
  - Zijn er submappen?  -> toon die submappen als albums (met een cover-foto).
  - Geen submappen, wel foto's? -> toon de foto's.
  - Niks van beide?     -> lege staat.

Extra's:
  - Favorieten (opgeslagen server-side in CACHE_DIR/favorites.json)
  - EXIF-informatie + GPS-locatie per foto

Alle configuratie via omgevingsvariabelen (zie docker-compose.yml):
  PHOTOS_ROOT  map met je foto's (read-only gemount)      default: /photos
  CACHE_DIR    map voor thumbnail-cache + favorieten       default: /cache
  THUMB_SIZE   standaard thumbnail-breedte in pixels        default: 400
"""

import hashlib
import json
import os
import threading
import time
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, render_template
from PIL import ExifTags, Image, ImageOps
from PIL.ExifTags import GPSTAGS, TAGS

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIC_SUPPORTED = True
except ImportError:
    # De container is nog niet herbouwd met pillow-heif in requirements.txt,
    # of het platform heeft geen wheel beschikbaar. HEIC-bestanden worden dan
    # gewoon overgeslagen i.p.v. de app te laten crashen.
    HEIC_SUPPORTED = False

PHOTOS_ROOT = Path(os.environ.get("PHOTOS_ROOT", "/photos")).resolve()
CACHE_DIR = Path(os.environ.get("CACHE_DIR", "/cache")).resolve()
DEFAULT_THUMB_SIZE = int(os.environ.get("THUMB_SIZE", "400"))
COVER_SEARCH_DEPTH = 3  # hoe diep we zoeken naar een omslagfoto voor een album-tegel
FAVORITES_FILE = CACHE_DIR / "favorites.json"
FAVORITES_PATH = "__favorites__"  # virtueel pad voor het favorieten-overzicht
CACHE_JOB_FILE = CACHE_DIR / "cache_job.json"
cache_job_lock = threading.Lock()  # voorkomt dat 2 cache-taken tegelijk starten binnen dit proces

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".heic", ".heif"}
HEIF_EXTS = {".heic", ".heif"}  # deze formaten kan geen enkele browser rechtstreeks tonen

CACHE_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)


# --------------------------------------------------------------------------
# Pad-helpers
# --------------------------------------------------------------------------

def safe_resolve(rel_path: str) -> Path:
    """Zet een relatief pad (van de client) om naar een absoluut pad,
    en blokkeert alles dat buiten PHOTOS_ROOT valt (path traversal)."""
    rel_path = (rel_path or "").strip("/")
    candidate = (PHOTOS_ROOT / rel_path).resolve()
    if candidate != PHOTOS_ROOT and PHOTOS_ROOT not in candidate.parents:
        abort(403)
    if not candidate.exists():
        abort(404)
    return candidate


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS and not path.name.startswith(".")


def find_cover(dir_path: Path, max_depth: int = COVER_SEARCH_DEPTH):
    """Zoekt de eerste foto (alfabetisch, ondiep-eerst) onder dir_path,
    zodat een album-tegel een voorbeeldfoto kan tonen."""
    try:
        entries = sorted(dir_path.iterdir(), key=lambda p: p.name.lower())
    except PermissionError:
        return None

    files = [p for p in entries if p.is_file() and is_image(p)]
    if files:
        return files[0]

    if max_depth <= 0:
        return None

    for sub in [p for p in entries if p.is_dir() and not p.name.startswith(".")]:
        cover = find_cover(sub, max_depth - 1)
        if cover:
            return cover
    return None


def rel(path: Path) -> str:
    return str(path.relative_to(PHOTOS_ROOT).as_posix())


# --------------------------------------------------------------------------
# Favorieten (server-side opgeslagen, zodat ze gelden voor iedereen die de
# app bezoekt, ongeacht browser/apparaat)
# --------------------------------------------------------------------------

def load_favorites() -> set:
    try:
        return set(json.loads(FAVORITES_FILE.read_text()))
    except Exception:
        return set()


def save_favorites(favs: set) -> None:
    FAVORITES_FILE.write_text(json.dumps(sorted(favs)))


# --------------------------------------------------------------------------
# EXIF-helpers
# --------------------------------------------------------------------------

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
    """Retourneert (dict met leesbare exif-tags, gps dict of None)."""
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


# --------------------------------------------------------------------------
# Routes - pagina
# --------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# --------------------------------------------------------------------------
# Routes - browsen
# --------------------------------------------------------------------------

@app.route("/api/browse")
def browse():
    rel_path = request.args.get("path", "")
    favs = load_favorites()

    if rel_path == FAVORITES_PATH:
        items = []
        for fav_path in sorted(favs):
            abs_p = PHOTOS_ROOT / fav_path
            if abs_p.is_file() and is_image(abs_p):
                items.append({"name": abs_p.name, "path": fav_path, "favorite": True})
        breadcrumbs = [{"name": "Favorieten", "path": FAVORITES_PATH}]
        return jsonify({"type": "photos", "path": FAVORITES_PATH, "breadcrumbs": breadcrumbs, "items": items})

    abs_path = safe_resolve(rel_path)

    if not abs_path.is_dir():
        abort(400, "Pad is geen map")

    try:
        entries = sorted(abs_path.iterdir(), key=lambda p: p.name.lower())
    except PermissionError:
        abort(403)

    subdirs = [p for p in entries if p.is_dir() and not p.name.startswith(".")]
    photos = [p for p in entries if p.is_file() and is_image(p)]

    breadcrumbs = []
    if rel_path.strip("/"):
        parts = rel_path.strip("/").split("/")
        for i, part in enumerate(parts):
            breadcrumbs.append({"name": part, "path": "/".join(parts[: i + 1])})

    if subdirs:
        items = []
        for d in subdirs:
            cover = find_cover(d)
            items.append(
                {
                    "name": d.name,
                    "path": rel(d),
                    "cover": rel(cover) if cover else None,
                }
            )
        return jsonify(
            {"type": "folders", "path": rel_path.strip("/"), "breadcrumbs": breadcrumbs, "items": items}
        )

    if photos:
        items = [{"name": p.name, "path": rel(p), "favorite": rel(p) in favs} for p in photos]
        return jsonify(
            {"type": "photos", "path": rel_path.strip("/"), "breadcrumbs": breadcrumbs, "items": items}
        )

    return jsonify(
        {"type": "empty", "path": rel_path.strip("/"), "breadcrumbs": breadcrumbs, "items": []}
    )


def ensure_thumbnail(abs_path: Path, size: int) -> Path:
    """Genereert (indien nodig) een thumbnail en retourneert het cache-bestand.
    Wordt gebruikt door zowel de /api/thumbnail-route als de bulk-cache-taak."""
    mtime = int(abs_path.stat().st_mtime)
    cache_key = hashlib.sha1(f"{abs_path}:{mtime}:{size}".encode()).hexdigest()
    cache_file = CACHE_DIR / f"{cache_key}.jpg"

    if not cache_file.exists():
        with Image.open(abs_path) as img:
            img = ImageOps.exif_transpose(img)  # respecteer rotatie uit EXIF
            img = img.convert("RGB")
            img.thumbnail((size, size))
            img.save(cache_file, "JPEG", quality=85)

    return cache_file


@app.route("/api/thumbnail")
def thumbnail():
    rel_path = request.args.get("path", "")
    size = int(request.args.get("size", DEFAULT_THUMB_SIZE))
    abs_path = safe_resolve(rel_path)

    if not abs_path.is_file() or not is_image(abs_path):
        abort(404)

    try:
        cache_file = ensure_thumbnail(abs_path, size)
    except Exception:
        abort(415, "Kan geen thumbnail maken van dit bestand")

    return send_file(cache_file, mimetype="image/jpeg")


@app.route("/api/image")
def full_image():
    rel_path = request.args.get("path", "")
    abs_path = safe_resolve(rel_path)

    if not abs_path.is_file() or not is_image(abs_path):
        abort(404)

    if abs_path.suffix.lower() in HEIF_EXTS:
        return serve_as_jpeg(abs_path)

    return send_file(abs_path)


def serve_as_jpeg(abs_path: Path):
    """Zet HEIC/HEIF om naar JPEG (browsers kunnen HEIC niet rechtstreeks
    weergeven), en cacht het resultaat zodat dit maar één keer per bestand
    hoeft te gebeuren."""
    if not HEIC_SUPPORTED:
        abort(415, "HEIC wordt niet ondersteund — herbouw de container met pillow-heif")

    mtime = int(abs_path.stat().st_mtime)
    cache_key = hashlib.sha1(f"{abs_path}:{mtime}:full-jpeg".encode()).hexdigest()
    cache_file = CACHE_DIR / f"{cache_key}_full.jpg"

    if not cache_file.exists():
        try:
            with Image.open(abs_path) as img:
                img = ImageOps.exif_transpose(img)
                img = img.convert("RGB")
                img.save(cache_file, "JPEG", quality=92)
        except Exception:
            abort(415, "Kan dit HEIC-bestand niet converteren")

    return send_file(cache_file, mimetype="image/jpeg")


# --------------------------------------------------------------------------
# Routes - favorieten
# --------------------------------------------------------------------------

@app.route("/api/favorites/toggle", methods=["POST"])
def toggle_favorite():
    body = request.get_json(force=True, silent=True) or {}
    abs_path = safe_resolve(body.get("path", ""))

    if not abs_path.is_file() or not is_image(abs_path):
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


# --------------------------------------------------------------------------
# Routes - EXIF
# --------------------------------------------------------------------------

@app.route("/api/exif")
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


# --------------------------------------------------------------------------
# Bulk-cache taak (voor de instellingenpagina: "Cache nu volledig aanmaken")
# --------------------------------------------------------------------------

def read_cache_job() -> dict:
    try:
        return json.loads(CACHE_JOB_FILE.read_text())
    except Exception:
        return {
            "status": "idle",
            "total": 0,
            "processed": 0,
            "skipped": 0,
            "started_at": None,
            "finished_at": None,
            "message": None,
        }


def write_cache_job(data: dict) -> None:
    CACHE_JOB_FILE.write_text(json.dumps(data))


def recover_stale_cache_job() -> None:
    """Bij een herstart van de container kan er een taak in het bestand staan
    met status 'running' terwijl het bijbehorende achtergrondproces allang
    niet meer bestaat (bijv. omdat de container werd gestopt). Zonder deze
    check zou de interface voor altijd op die 'lopende' taak blijven wachten
    en de knoppen uitgeschakeld houden. We markeren zo'n taak daarom als
    'interrupted' zodra de app opnieuw opstart."""
    job = read_cache_job()
    if job.get("status") == "running":
        job["status"] = "interrupted"
        job["finished_at"] = time.time()
        write_cache_job(job)


recover_stale_cache_job()  # meteen uitvoeren bij het opstarten van de app


def run_cache_job() -> None:
    job = {
        "status": "running",
        "total": 0,
        "processed": 0,
        "skipped": 0,
        "started_at": time.time(),
        "finished_at": None,
        "message": "Foto's aan het tellen...",
    }
    write_cache_job(job)

    try:
        all_images = [p for p in PHOTOS_ROOT.rglob("*") if p.is_file() and is_image(p)]
        job["total"] = len(all_images)
        job["message"] = None
        write_cache_job(job)

        for i, p in enumerate(all_images, start=1):
            try:
                ensure_thumbnail(p, DEFAULT_THUMB_SIZE)
            except Exception:
                job["skipped"] += 1  # bijv. een corrupt bestand; taak gaat gewoon door
            job["processed"] = i
            if i % 10 == 0 or i == job["total"]:
                write_cache_job(job)

        job["status"] = "done"
        job["finished_at"] = time.time()
        write_cache_job(job)
    except Exception as e:
        job["status"] = "error"
        job["message"] = str(e)
        job["finished_at"] = time.time()
        write_cache_job(job)


@app.route("/api/cache/info")
def cache_info():
    total_images = sum(1 for p in PHOTOS_ROOT.rglob("*") if p.is_file() and is_image(p))
    cache_files = list(CACHE_DIR.glob("*.jpg"))
    return jsonify(
        {
            "total_images": total_images,
            "cached_files": len(cache_files),
            "cache_size_bytes": sum(p.stat().st_size for p in cache_files),
        }
    )


@app.route("/api/cache/status")
def cache_status():
    return jsonify(read_cache_job())


@app.route("/api/cache/start", methods=["POST"])
def start_cache_job():
    with cache_job_lock:
        current = read_cache_job()
        if current.get("status") == "running":
            return jsonify(current)

        thread = threading.Thread(target=run_cache_job, daemon=True)
        thread.start()

    return jsonify(read_cache_job())


@app.route("/api/cache/clear", methods=["POST"])
def clear_cache():
    current = read_cache_job()
    if current.get("status") == "running":
        abort(409, "Er loopt al een cache-taak — wacht tot deze klaar is voordat je de cache leegt.")

    removed = 0
    for p in CACHE_DIR.glob("*.jpg"):
        try:
            p.unlink()
            removed += 1
        except Exception:
            pass

    return jsonify({"removed": removed})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
