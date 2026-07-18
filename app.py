"""
Simple, self-contained album viewer (no Immich required).

Folder logic:
  - Does the folder contain subfolders?  -> show those subfolders as albums (with a cover photo).
  - No subfolders, but photos?           -> show the photos.
  - Neither?                             -> empty state.

Extras:
  - Login required (single account, created on first visit via /setup)
  - Favorites (stored server-side in CACHE_DIR/favorites.json)
  - EXIF info + GPS location per photo
  - Bulk thumbnail caching job (for the settings panel)

All configuration via environment variables (see docker-compose.yml):
  PHOTOS_ROOT  folder with your photos (mounted read-only)   default: /photos
  CACHE_DIR    folder for thumbnail cache + app data          default: /cache
  THUMB_SIZE   default thumbnail width in pixels               default: 400
"""

import hashlib
import json
import os
import secrets
import threading
import time
from datetime import timedelta
from pathlib import Path

from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from PIL import ExifTags, Image, ImageOps
from PIL.ExifTags import GPSTAGS, TAGS
from werkzeug.security import check_password_hash, generate_password_hash

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIC_SUPPORTED = True
except ImportError:
    # The container hasn't been rebuilt with pillow-heif in requirements.txt yet,
    # or no wheel is available for this platform. HEIC files are simply skipped
    # instead of crashing the app.
    HEIC_SUPPORTED = False

PHOTOS_ROOT = Path(os.environ.get("PHOTOS_ROOT", "/photos")).resolve()
CACHE_DIR = Path(os.environ.get("CACHE_DIR", "/cache")).resolve()
DEFAULT_THUMB_SIZE = int(os.environ.get("THUMB_SIZE", "400"))
COVER_SEARCH_DEPTH = 3  # how deep we search for a cover photo for an album tile
FAVORITES_FILE = CACHE_DIR / "favorites.json"
FAVORITES_PATH = "__favorites__"  # virtual path for the favorites overview
CACHE_JOB_FILE = CACHE_DIR / "cache_job.json"
cache_job_lock = threading.Lock()  # prevents two cache jobs starting at once within this process
GPS_INDEX_FILE = CACHE_DIR / "gps_index.json"
gps_index_lock = threading.Lock()  # guards read-modify-write of the GPS index within this process

ACCOUNT_FILE = CACHE_DIR / "account.json"
SECRET_KEY_FILE = CACHE_DIR / "secret_key.txt"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".heic", ".heif"}
HEIF_EXTS = {".heic", ".heif"}  # no browser can display these formats directly

CACHE_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)


def get_or_create_secret_key() -> str:
    """Persists a random Flask session-signing key in CACHE_DIR, so login
    sessions survive an app/container restart instead of everyone being
    logged out every time."""
    if SECRET_KEY_FILE.exists():
        return SECRET_KEY_FILE.read_text().strip()
    key = secrets.token_hex(32)
    SECRET_KEY_FILE.write_text(key)
    return key


app.config["SECRET_KEY"] = get_or_create_secret_key()
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------

def account_exists() -> bool:
    return ACCOUNT_FILE.exists()


def load_account():
    try:
        return json.loads(ACCOUNT_FILE.read_text())
    except Exception:
        return None


def save_account(username: str, password: str) -> None:
    ACCOUNT_FILE.write_text(
        json.dumps({"username": username, "password_hash": generate_password_hash(password)})
    )


# Endpoints reachable without being logged in (auth pages + static assets).
PUBLIC_ENDPOINTS = {"setup", "login", "static"}


@app.before_request
def require_login():
    if request.endpoint in PUBLIC_ENDPOINTS:
        return None

    if not account_exists():
        return redirect(url_for("setup"))

    if not session.get("logged_in"):
        return redirect(url_for("login", next=request.path))

    return None


@app.route("/setup", methods=["GET", "POST"])
def setup():
    # Only usable once: as soon as an account exists, this route just bounces to /login.
    if account_exists():
        return redirect(url_for("login"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        if not username or not password:
            error = "Vul een gebruikersnaam en wachtwoord in."
        elif password != password_confirm:
            error = "Wachtwoorden komen niet overeen."
        elif len(password) < 6:
            error = "Wachtwoord moet minstens 6 tekens lang zijn."
        else:
            save_account(username, password)
            session.clear()
            session["logged_in"] = True
            session["username"] = username
            session.permanent = True
            return redirect(url_for("index"))

    return render_template("setup.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    if not account_exists():
        return redirect(url_for("setup"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        account = load_account()

        if account and username == account.get("username") and check_password_hash(
            account.get("password_hash", ""), password
        ):
            session.clear()
            session["logged_in"] = True
            session["username"] = username
            session.permanent = True
            next_path = request.args.get("next")
            return redirect(next_path if next_path else url_for("index"))

        error = "Onjuiste gebruikersnaam of wachtwoord."

    return render_template("login.html", error=error)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# --------------------------------------------------------------------------
# Path helpers
# --------------------------------------------------------------------------

def safe_resolve(rel_path: str) -> Path:
    """Turns a relative path (from the client) into an absolute path, and
    blocks anything that falls outside PHOTOS_ROOT (path traversal)."""
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
    """Finds the first photo (alphabetically, shallowest first) under
    dir_path, so an album tile can show a preview photo."""
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
# Favorites (stored server-side, so they apply to everyone visiting the
# app, regardless of browser/device)
# --------------------------------------------------------------------------

def load_favorites() -> set:
    try:
        return set(json.loads(FAVORITES_FILE.read_text()))
    except Exception:
        return set()


def save_favorites(favs: set) -> None:
    FAVORITES_FILE.write_text(json.dumps(sorted(favs)))


# --------------------------------------------------------------------------
# EXIF helpers
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


# --------------------------------------------------------------------------
# Routes - page
# --------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# --------------------------------------------------------------------------
# Routes - browsing
# --------------------------------------------------------------------------

DEFAULT_PAGE_SIZE = 300
MAX_PAGE_SIZE = 1000


def paginate(items: list, offset: int, limit: int):
    total = len(items)
    page = items[offset : offset + limit]
    has_more = offset + limit < total
    return page, total, has_more


@app.route("/api/browse")
def browse():
    rel_path = request.args.get("path", "")
    favs = load_favorites()

    offset = max(0, request.args.get("offset", default=0, type=int) or 0)
    limit = request.args.get("limit", default=DEFAULT_PAGE_SIZE, type=int) or DEFAULT_PAGE_SIZE
    limit = max(1, min(limit, MAX_PAGE_SIZE))

    if rel_path == FAVORITES_PATH:
        all_favs = sorted(favs)
        page_favs, total, has_more = paginate(all_favs, offset, limit)
        items = []
        for fav_path in page_favs:
            abs_p = PHOTOS_ROOT / fav_path
            if abs_p.is_file() and is_image(abs_p):
                items.append({"name": abs_p.name, "path": fav_path, "favorite": True})
        breadcrumbs = [{"name": "Favorieten", "path": FAVORITES_PATH}]
        return jsonify(
            {
                "type": "photos",
                "path": FAVORITES_PATH,
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
    photos = [p for p in entries if p.is_file() and is_image(p)]

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

    if photos:
        page_photos, total, has_more = paginate(photos, offset, limit)
        items = [{"name": p.name, "path": rel(p), "favorite": rel(p) in favs} for p in page_photos]
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


def load_gps_index() -> dict:
    try:
        return json.loads(GPS_INDEX_FILE.read_text())
    except Exception:
        return {}


def save_gps_index(index: dict) -> None:
    GPS_INDEX_FILE.write_text(json.dumps(index))


def record_gps(rel_path: str, name: str, mtime: int, gps) -> None:
    with gps_index_lock:
        index = load_gps_index()
        index[rel_path] = {
            "mtime": mtime,
            "name": name,
            "lat": gps["lat"] if gps else None,
            "lon": gps["lon"] if gps else None,
        }
        save_gps_index(index)


def ensure_thumbnail(abs_path: Path, size: int) -> Path:
    """Generates (if needed) a thumbnail and returns the cache file.
    Used by both the /api/thumbnail route and the bulk-cache job.

    While the file is open anyway, this also opportunistically checks
    whether its GPS location has been recorded yet in the GPS index (used
    by the map overview), so browsing/caching photos gradually builds up
    the map data without a separate full-library scan."""
    mtime = int(abs_path.stat().st_mtime)
    cache_key = hashlib.sha1(f"{abs_path}:{mtime}:{size}".encode()).hexdigest()
    cache_file = CACHE_DIR / f"{cache_key}.jpg"

    normalized = rel(abs_path)
    gps_entry = load_gps_index().get(normalized)
    needs_gps_check = gps_entry is None or gps_entry.get("mtime") != mtime
    needs_thumb = not cache_file.exists()

    if needs_thumb or needs_gps_check:
        with Image.open(abs_path) as img:
            if needs_gps_check:
                _, gps = read_exif(img)
                record_gps(normalized, abs_path.name, mtime, gps)

            if needs_thumb:
                thumb_img = ImageOps.exif_transpose(img)  # respect rotation from EXIF
                thumb_img = thumb_img.convert("RGB")
                thumb_img.thumbnail((size, size))
                thumb_img.save(cache_file, "JPEG", quality=85)

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
    """Converts HEIC/HEIF to JPEG (browsers can't display HEIC directly),
    and caches the result so this only has to happen once per file."""
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
# Routes - favorites
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
# Routes - map overview
# --------------------------------------------------------------------------

@app.route("/api/map/photos")
def map_photos():
    """Returns every photo that has a known GPS location, for the map
    overview. Backed by the GPS index built up in ensure_thumbnail(), so
    this stays fast even for large libraries — no re-scanning of files here."""
    favs = load_favorites()
    index = load_gps_index()

    items = []
    for rel_path, entry in index.items():
        lat, lon = entry.get("lat"), entry.get("lon")
        if lat is None or lon is None:
            continue
        if not (PHOTOS_ROOT / rel_path).is_file():
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


# --------------------------------------------------------------------------
# Bulk-cache job (for the settings panel: "Cache nu volledig aanmaken")
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
    """After a container restart, the job file might still say 'running'
    even though the background thread that owned it is long gone (e.g.
    because the container was stopped). Without this check, the UI would
    wait forever on that 'running' job and keep the buttons disabled. So we
    mark such a job as 'interrupted' as soon as the app starts up again."""
    job = read_cache_job()
    if job.get("status") == "running":
        job["status"] = "interrupted"
        job["finished_at"] = time.time()
        write_cache_job(job)


recover_stale_cache_job()  # run immediately when the app starts


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
                job["skipped"] += 1  # e.g. a corrupt file; the job just continues
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
