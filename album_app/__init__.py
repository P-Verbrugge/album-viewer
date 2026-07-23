"""
Application factory for the album viewer.

Each feature area lives in its own module (auth, account_routes,
admin_users, browse, favorites, media_routes, exif_routes, gps_map,
cache_job, downloads, pages), registered here as a Flask Blueprint. Shared
configuration lives in config.py, and shared media-handling logic (path
safety, thumbnails, GPS index) lives in media.py.
"""

from datetime import timedelta
from pathlib import Path

from flask import Flask

from . import (
    account_routes,
    admin_users,
    auth,
    browse,
    cache_job,
    downloads,
    exif_routes,
    favorites,
    gps_map,
    media_routes,
    pages,
)

# album_app/__init__.py lives one level below the project root, but the
# templates/ and static/ folders live at the project root (that's also
# where the Dockerfile COPYs them to). Flask's default root_path would
# otherwise be this package's own folder, which would make it look for
# templates/static in the wrong place.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(PROJECT_ROOT / "templates"),
        static_folder=str(PROJECT_ROOT / "static"),
    )

    app.config["SECRET_KEY"] = auth.get_or_create_secret_key()
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    app.before_request(auth.require_login)

    app.register_blueprint(pages.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(account_routes.bp)
    app.register_blueprint(admin_users.bp)
    app.register_blueprint(browse.bp)
    app.register_blueprint(media_routes.bp)
    app.register_blueprint(favorites.bp)
    app.register_blueprint(exif_routes.bp)
    app.register_blueprint(gps_map.bp)
    app.register_blueprint(downloads.bp)
    app.register_blueprint(cache_job.bp)

    # Installations from before multi-user support have a single account.json
    # — turn it into the first admin user instead of forcing a fresh /setup.
    auth.migrate_legacy_account()

    # A cache job left "running" by a container restart would otherwise
    # block the settings UI forever — fix that up right away on startup.
    cache_job.recover_stale_cache_job()

    return app
