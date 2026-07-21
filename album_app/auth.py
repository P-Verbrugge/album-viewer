"""
Authentication: a single account, created on first visit via /setup, backed
by a Flask session. Also registers the before_request guard that protects
every other route in the app.
"""

import json
import secrets

from flask import Blueprint, redirect, render_template, request, session, url_for
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


def account_exists() -> bool:
    return config.ACCOUNT_FILE.exists()


def load_account():
    try:
        return json.loads(config.ACCOUNT_FILE.read_text())
    except Exception:
        return None


def save_account(username: str, password: str) -> None:
    config.ACCOUNT_FILE.write_text(
        json.dumps({"username": username, "password_hash": generate_password_hash(password)})
    )


def require_login():
    """Registered as a before_request hook by create_app(). Redirects to
    /setup (no account yet) or /login (not signed in) for every route except
    the public ones above."""
    if request.endpoint in PUBLIC_ENDPOINTS:
        return None

    if not account_exists():
        return redirect(url_for("auth.setup"))

    if not session.get("logged_in"):
        return redirect(url_for("auth.login", next=request.path))

    return None


@bp.route("/setup", methods=["GET", "POST"])
def setup():
    # Only usable once: as soon as an account exists, this route just bounces to /login.
    if account_exists():
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
            save_account(username, password)
            session.clear()
            session["logged_in"] = True
            session["username"] = username
            session.permanent = True
            return redirect(url_for("pages.index"))

    return render_template("setup.html", error=error)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if not account_exists():
        return redirect(url_for("auth.setup"))

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
            return redirect(next_path if next_path else url_for("pages.index"))

        error = "Onjuiste gebruikersnaam of wachtwoord."

    return render_template("login.html", error=error)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
