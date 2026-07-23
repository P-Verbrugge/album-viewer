"""
Authentication: multiple named accounts (one of which can be an admin),
backed by a Flask session. Also registers the before_request guard that
protects every other route in the app, and migrates a pre-multi-user
installation's single account.json into the new users.json store.
"""

import json
import secrets

from flask import Blueprint, abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from . import config

bp = Blueprint("auth", __name__)

# Endpoints reachable without being logged in (auth pages + static assets).
PUBLIC_ENDPOINTS = {"auth.setup", "auth.login", "static"}


def get_or_create_secret_key() -> str:
    """Persists a random Flask session-signing key in CACHE_DIR, so login
    sessions survive an app/container restart instead of everyone being
    logged out every time."""
    if config.SECRET_KEY_FILE.exists():
        return config.SECRET_KEY_FILE.read_text().strip()
    key = secrets.token_hex(32)
    config.SECRET_KEY_FILE.write_text(key)
    return key


# --------------------------------------------------------------------------
# User store: { "username": {"password_hash": ..., "is_admin": bool} }
# --------------------------------------------------------------------------

def load_users() -> dict:
    try:
        return json.loads(config.USERS_FILE.read_text())
    except Exception:
        return {}


def save_users(users: dict) -> None:
    config.USERS_FILE.write_text(json.dumps(users))


def any_users_exist() -> bool:
    return len(load_users()) > 0


def get_user(username: str):
    return load_users().get(username)


def count_admins(users: dict = None) -> int:
    users = users if users is not None else load_users()
    return sum(1 for u in users.values() if u.get("is_admin"))


def create_user(username: str, password: str, is_admin: bool = False) -> None:
    with config.users_lock:
        users = load_users()
        users[username] = {"password_hash": generate_password_hash(password), "is_admin": is_admin}
        save_users(users)


def delete_user(username: str) -> None:
    with config.users_lock:
        users = load_users()
        users.pop(username, None)
        save_users(users)
    # Clean up their personal favorites too, since that username no longer exists.
    from .favorites import delete_user_favorites
    delete_user_favorites(username)


def set_password(username: str, new_password: str) -> None:
    with config.users_lock:
        users = load_users()
        if username in users:
            users[username]["password_hash"] = generate_password_hash(new_password)
            save_users(users)


def set_admin(username: str, is_admin: bool) -> None:
    with config.users_lock:
        users = load_users()
        if username in users:
            users[username]["is_admin"] = is_admin
            save_users(users)


def current_user():
    username = session.get("username")
    if not username:
        return None
    user = get_user(username)
    if user is None:
        return None
    return {"username": username, **user}


def require_admin():
    user = current_user()
    if not user or not user.get("is_admin"):
        abort(403)
    return user


def migrate_legacy_account() -> None:
    """Installations from before multi-user support have a single
    CACHE_DIR/account.json. If no users.json exists yet but that legacy file
    does, turn it into the first (admin) user instead of forcing a fresh
    /setup — nobody should lose their existing login over this upgrade."""
    if config.USERS_FILE.exists():
        return
    if not config.ACCOUNT_FILE.exists():
        return
    try:
        legacy = json.loads(config.ACCOUNT_FILE.read_text())
        username = legacy["username"]
        password_hash = legacy["password_hash"]
    except Exception:
        return

    save_users({username: {"password_hash": password_hash, "is_admin": True}})
    config.ACCOUNT_FILE.rename(config.ACCOUNT_FILE.with_suffix(".json.migrated"))


def require_login():
    """Registered as a before_request hook by create_app(). Redirects to
    /setup (no account yet) or /login (not signed in, or the account behind
    this session was since deleted) for every route except the public ones
    above."""
    if request.endpoint in PUBLIC_ENDPOINTS:
        return None

    if not any_users_exist():
        return redirect(url_for("auth.setup"))

    if not session.get("logged_in"):
        return redirect(url_for("auth.login", next=request.path))

    username = session.get("username")
    if not username or not get_user(username):
        # The account behind this session no longer exists (e.g. an admin
        # deleted it) — end the stale session instead of half-trusting it.
        session.clear()
        return redirect(url_for("auth.login", next=request.path))

    return None


@bp.route("/setup", methods=["GET", "POST"])
def setup():
    # Only usable once: as soon as any user exists, this route just bounces to /login.
    if any_users_exist():
        return redirect(url_for("auth.login"))

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
            # The very first account is always the admin.
            create_user(username, password, is_admin=True)
            session.clear()
            session["logged_in"] = True
            session["username"] = username
            session.permanent = True
            return redirect(url_for("pages.index"))

    return render_template("setup.html", error=error)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if not any_users_exist():
        return redirect(url_for("auth.setup"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_user(username)

        if user and check_password_hash(user.get("password_hash", ""), password):
            session.clear()
            session["logged_in"] = True
            session["username"] = username
            session.permanent = True
            next_path = request.args.get("next")
            return redirect(next_path if next_path else url_for("pages.index"))

        error = "Onjuiste gebruikersnaam of wachtwoord."

    return render_template("login.html", error=error)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
