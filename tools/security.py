"""Модуль с функциями безопасности: проверка CSRF, проверка same-origin и комбинированный декоратор аутентификации."""

from __future__ import annotations

import secrets
from functools import wraps
from urllib.parse import urlparse
from collections.abc import Callable

from flask import Request, jsonify, request, session


def ensure_csrf() -> str:
    """
    Возвращает CSRF-токен из сессии.
    Если его нет — генерирует новый и сохраняет в сессии.
    """
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def check_csrf(req: Request) -> bool:
    """
    Проверяет корректность CSRF-токена.

    Источники:
      - поле формы `csrf_token`
      - HTTP-заголовок `X-CSRF-Token`

    Возвращает `True`, если токен есть и он совпадает с токеном в сессии.
    """
    token = req.form.get("csrf_token") or req.headers.get("X-CSRF-Token")
    return bool(token) and token == session.get("csrf_token")


def same_origin(req: Request, allowed_origin: str | None) -> bool:
    """
    Проверка, что запрос сделан с разрешённого источника (same-origin).

    Разрешаем:
      - если `Origin` или `Referer` совпадает с `allowed_origin` (если он задан),
        иначе сравниваем с `req.host`
      - если оба заголовка отсутствуют, считаем same-origin (например, curl)
      - в режиме разработки (`localhost` и `127.0.0.1`) допускаем их взаимозаменяемость

    Возвращает `True`, если источник корректный, иначе `False`.
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

        # Нет заголовков Origin/Referer — считаем, что это same-origin
        return not origin and not referer
    except Exception:
        return False


def auth_bearer_or_same_origin_csrf(token_manager, allowed_origin: str | None) -> Callable:
    """
    Декоратор для защиты эндпоинтов.

    Пускает запрос только если выполняется одно из условий:
      1. Прислан Bearer-токен, который проходит проверку через `token_manager.is_valid_token`.
      2. Запрос сделан с того же источника (same-origin) **и** CSRF-токен корректный.

    В противном случае возвращает ошибку:
      - `401 Unauthorized`, если источник не совпадает
      - `401`, если CSRF отсутствует или невалиден
      - `403 Forbidden`, если Bearer-токен передан, но он недействителен
    """

    def decorator(f: Callable) -> Callable:
        @wraps(f)
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

        return wrapper

    return decorator
