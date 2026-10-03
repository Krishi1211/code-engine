import os
import re
from functools import wraps

from flask import request, jsonify, g
from itsdangerous import URLSafeTimedSerializer, BadSignature
from werkzeug.security import generate_password_hash, check_password_hash

from tasks import r

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    # tokens stop working when the server restarts unless SECRET_KEY is set
    SECRET_KEY = os.urandom(32).hex()

TOKEN_MAX_AGE = 24 * 3600
USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")

serializer = URLSafeTimedSerializer(SECRET_KEY, salt="auth")


def user_key(username):
    return f"user:{username}"


def register_user(username, password):
    if not USERNAME_RE.match(username or ""):
        return "username must be 3-32 letters, digits, _ or -"
    if not password or len(password) < 8:
        return "password must be at least 8 characters"
    if not r.hsetnx(user_key(username), "password", generate_password_hash(password)):
        return "username already taken"
    return None


def check_login(username, password):
    stored = r.hget(user_key(username or ""), "password")
    return bool(stored) and check_password_hash(stored, password or "")


def make_token(username):
    return serializer.dumps({"user": username})


def user_from_token(token):
    try:
        return serializer.loads(token, max_age=TOKEN_MAX_AGE)["user"]
    except (BadSignature, KeyError, TypeError):
        return None


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        user = user_from_token(header[7:]) if header.startswith("Bearer ") else None
        if not user:
            return jsonify({"error": "authentication required"}), 401
        g.user = user
        return fn(*args, **kwargs)
    return wrapper
