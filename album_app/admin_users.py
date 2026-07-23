"""
Admin-only user management: list/create/delete users, reset a user's
password, and toggle admin status. Every route here requires the logged-in
user to be an admin (checked fresh against the user store on every request,
not just trusted from the session).
"""

from flask import Blueprint, abort, jsonify, request, session

from .auth import count_admins, create_user, delete_user, get_user, load_users, require_admin, set_admin, set_password

bp = Blueprint("admin_users", __name__)


@bp.route("/api/admin/users")
def list_users():
    require_admin()
    users = load_users()
    return jsonify(
        {
            "users": [
                {"username": username, "is_admin": bool(u.get("is_admin"))}
                for username, u in sorted(users.items())
            ]
        }
    )


@bp.route("/api/admin/users", methods=["POST"])
def add_user():
    require_admin()
    body = request.get_json(force=True, silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    is_admin = bool(body.get("is_admin"))

    if not username or not password:
        return jsonify({"error": "Vul een gebruikersnaam en wachtwoord in."}), 400
    if len(password) < 6:
        return jsonify({"error": "Wachtwoord moet minstens 6 tekens lang zijn."}), 400
    if get_user(username):
        return jsonify({"error": "Deze gebruikersnaam bestaat al."}), 400

    create_user(username, password, is_admin)
    return jsonify({"username": username, "is_admin": is_admin})


@bp.route("/api/admin/users/<username>", methods=["DELETE"])
def remove_user(username):
    require_admin()

    if username == session.get("username"):
        return jsonify({"error": "Je kunt je eigen account niet verwijderen."}), 400

    user = get_user(username)
    if not user:
        abort(404)

    if user.get("is_admin") and count_admins() <= 1:
        return jsonify({"error": "Er moet minstens \u00e9\u00e9n beheerder overblijven."}), 400

    delete_user(username)
    return jsonify({"ok": True})


@bp.route("/api/admin/users/<username>/password", methods=["POST"])
def reset_password(username):
    require_admin()

    if not get_user(username):
        abort(404)

    body = request.get_json(force=True, silent=True) or {}
    new_password = body.get("new_password") or ""
    if len(new_password) < 6:
        return jsonify({"error": "Wachtwoord moet minstens 6 tekens lang zijn."}), 400

    set_password(username, new_password)
    return jsonify({"ok": True})


@bp.route("/api/admin/users/<username>/admin", methods=["POST"])
def toggle_admin(username):
    require_admin()

    user = get_user(username)
    if not user:
        abort(404)

    body = request.get_json(force=True, silent=True) or {}
    is_admin = bool(body.get("is_admin"))

    if not is_admin and user.get("is_admin") and count_admins() <= 1:
        return jsonify({"error": "Er moet minstens \u00e9\u00e9n beheerder overblijven."}), 400

    set_admin(username, is_admin)
    return jsonify({"username": username, "is_admin": is_admin})
