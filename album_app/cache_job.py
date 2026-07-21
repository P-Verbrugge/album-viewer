"""
The bulk-cache job used by the settings panel ("Cache nu volledig
aanmaken"): walks the whole library in a background thread, generating any
missing thumbnails, with progress reported via a small JSON status file.
"""

import json
import threading
import time

from flask import Blueprint, abort, jsonify

from . import config
from .media import ensure_thumbnail, is_media

bp = Blueprint("cache_job", __name__)


def read_cache_job() -> dict:
    try:
        return json.loads(config.CACHE_JOB_FILE.read_text())
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
    config.CACHE_JOB_FILE.write_text(json.dumps(data))


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
        all_images = [p for p in config.PHOTOS_ROOT.rglob("*") if p.is_file() and is_media(p)]
        job["total"] = len(all_images)
        job["message"] = None
        write_cache_job(job)

        for i, p in enumerate(all_images, start=1):
            try:
                ensure_thumbnail(p, config.DEFAULT_THUMB_SIZE)
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


@bp.route("/api/cache/info")
def cache_info():
    total_images = sum(1 for p in config.PHOTOS_ROOT.rglob("*") if p.is_file() and is_media(p))
    cache_files = list(config.CACHE_DIR.glob("*.jpg"))
    return jsonify(
        {
            "total_images": total_images,
            "cached_files": len(cache_files),
            "cache_size_bytes": sum(p.stat().st_size for p in cache_files),
        }
    )


@bp.route("/api/cache/status")
def cache_status():
    return jsonify(read_cache_job())


@bp.route("/api/cache/start", methods=["POST"])
def start_cache_job():
    with config.cache_job_lock:
        current = read_cache_job()
        if current.get("status") == "running":
            return jsonify(current)

        thread = threading.Thread(target=run_cache_job, daemon=True)
        thread.start()

    return jsonify(read_cache_job())


@bp.route("/api/cache/clear", methods=["POST"])
def clear_cache():
    current = read_cache_job()
    if current.get("status") == "running":
        abort(409, "Er loopt al een cache-taak — wacht tot deze klaar is voordat je de cache leegt.")

    removed = 0
    for p in config.CACHE_DIR.glob("*.jpg"):
        try:
            p.unlink()
            removed += 1
        except Exception:
            pass

    return jsonify({"removed": removed})
