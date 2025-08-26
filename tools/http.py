"""Вспомогательные HTTP-утилиты для Flask-обработчиков."""

from __future__ import annotations

from flask import Response, jsonify

from logger.logger import app_logger

__all__ = ["bad_request", "server_error", "handle_413"]


def bad_request(msg: str, code: int = 400) -> tuple[Response, int]:
    """Сформировать JSON-ответ для 4xx-ошибок клиента.

    Логирует сообщение на уровне WARNING и возвращает кортеж (Response, status_code).
    :param msg: Текст ошибки для пользователя
    :param code: HTTP-код (по умолчанию 400)
    """
    app_logger.warning("Bad request: %s", msg)
    return jsonify({"error": msg}), code


def server_error(msg: str = "Internal server error") -> tuple[Response, int]:
    """Сформировать JSON-ответ для 5xx-ошибок сервера.

    Логирует сообщение на уровне ERROR и возвращает кортеж (Response, 500).
    :param msg: Текст ошибки (по умолчанию 'Internal server error')
    """
    app_logger.error("Server error: %s", msg)
    return jsonify({"error": msg}), 500


def handle_413(max_content_length: int):
    """Фабрика обработчика ошибки 413 (слишком большой запрос).

    Возвращает функцию-обработчик, совместимую с `app.register_error_handler(413, ...)`,
    которая отдает JSON с человекочитаемым лимитом в мегабайтах.

    :param max_content_length: Максимальный размер тела запроса в байтах
    :return: callable, принимающий исключение и возвращающий (Response, 413)
    """

    def _handler(_e) -> tuple[Response, int]:
        """Внутренний обработчик 413: пишет в лог и возвращает JSON-ответ."""
        app_logger.error("Request entity too large")
        mb = max_content_length / (1024 * 1024)
        return jsonify({"error": f"The total upload is too large (> {mb} MB)."}), 413

    return _handler
