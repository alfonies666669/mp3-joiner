import secrets
from urllib.parse import urlparse

from flask import jsonify, request, session


def ensure_csrf():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def check_csrf(req) -> bool:
    token = req.form.get("csrf_token") or req.headers.get("X-CSRF-Token")
    return bool(token) and token == session.get("csrf_token")


def same_origin(req, allowed_origin: str | None) -> bool:
    """
    Разрешаем:
      - Origin/Referer == ALLOWED_ORIGIN (если задан)
      - ИЛИ, если хедеров нет, считаем same-origin
      - Для дев-режима считаем localhost и 127.0.0.1 взаимозаменяемыми
    """
    try:
        expected = urlparse(allowed_origin).netloc if allowed_origin else req.host
        exp_hosts = {expected}
        if expected.startswith("localhost:"):
            exp_hosts.add(expected.replace("localhost", "127.0.0.1"))
        if expected.startswith("127.0.0.1:"):
            exp_hosts.add(expected.replace("127.0.0.1", "localhost"))

        origin = req.headers.get("Origin")
        if origin and urlparse(origin).netloc in exp_hosts:
            return True
        referer = req.headers.get("Referer")
        if referer and urlparse(referer).netloc in exp_hosts:
            return True
        return not origin and not referer
    except Exception:
        return False


def auth_bearer_or_same_origin_csrf(token_manager, allowed_origin: str | None):
    """
    Декоратор: пускаем ИЛИ по Bearer, ИЛИ по same-origin+CSRF.
    """

    def decorator(f):
        def wrapper(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                token = auth.replace("Bearer ", "", 1).strip()
                if token_manager and not token_manager.is_valid_token(token):
                    return jsonify({"error": "Forbidden"}), 403
                return f(*args, **kwargs)
            if same_origin(request, allowed_origin) and check_csrf(request):
                return f(*args, **kwargs)
            if not same_origin(request, allowed_origin):
                return jsonify({"error": "Unauthorized"}), 401
            return jsonify({"error": "CSRF token missing or invalid"}), 401

        wrapper.__name__ = f.__name__
        return wrapper

    return decorator
