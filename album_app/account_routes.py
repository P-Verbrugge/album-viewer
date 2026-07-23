"""Self-service account routes: who am I, and changing your own password."""

from flask import Blueprint, abort, jsonify, request, session
from werkzeug.security import check_password_hash

from .auth import current_user, get_user, set_password

bp = Blueprint("account_routes", __name__)


@bp.route("/api/account/me")
def me():
    user = current_user()
    if not user:
        abort(401)
    return jsonify({"username": user["username"], "is_admin": bool(user.get("is_admin"))})


@bp.route("/api/account/password", methods=["POST"])
def change_password():
    username = session.get("username")
    user = get_user(username)
    if not user:
        abort(401)

    body = request.get_json(force=True, silent=True) or {}
    current_password = body.get("current_password", "")
    new_password = body.get("new_password", "")

    if not check_password_hash(user.get("password_hash", ""), current_password):
        return jsonify({"error": "Huidig wachtwoord is onjuist."}), 400
    if len(new_password) < 6:
        return jsonify({"error": "Nieuw wachtwoord moet minstens 6 tekens lang zijn."}), 400

    set_password(username, new_password)
    return jsonify({"ok": True})
