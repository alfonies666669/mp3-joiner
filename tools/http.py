"""Вспомогательные HTTP-утилиты для Flask-обработчиков."""

from __future__ import annotations

from flask import Response, jsonify

from logger.logger import app_logger

__all__ = ["bad_request", "server_error", "handle_413"]


def bad_request(msg: str, code: int = 400) -> tuple[Response, int]:
    """Сформировать JSON-ответ для 4xx-ошибок клиента."""
    app_logger.warning("Bad request: %s", msg)
    return jsonify({"error": msg}), code


def server_error(msg: str = "Internal server error") -> tuple[Response, int]:
    """Сформировать JSON-ответ для 5xx-ошибок сервера."""
    app_logger.error("Server error: %s", msg)
    return jsonify({"error": msg}), 500


def handle_413(max_content_length: int):
    """Фабрика обработчика ошибки 413 (слишком большой запрос)."""

    def _handler(_e) -> tuple[Response, int]:
        app_logger.error("Request entity too large")
        mb = max_content_length / (1024 * 1024)
        return jsonify({"error": f"The total upload is too large (> {mb} MB)."}), 413

    return _handler
