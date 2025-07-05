import os
from functools import wraps

import requests
from flask import Blueprint, jsonify, request

from logger.logger import user_logger


class IPGeoTokenManager:
    """
    Класс, предоставляющий методы для работы с токенами.
    """

    def __init__(self, token_file, logger=None):
        self.token_file = token_file
        self.logger = logger or user_logger or (lambda *a, **k: None)
        self.allowed_tokens = self.load_allowed_tokens()

    def _log(self, event, level="info", **kwargs):
        """
        Логирует событие через user_logger (если есть), иначе print.
        Все поля пишутся в extra (для JSON-логов).
        """
        log_data = {"event": event}
        log_data.update(kwargs)
        logger = self.logger
        if logger and hasattr(logger, level):
            log_func = getattr(logger, level)
            log_func(event, extra={"extra": log_data})
        else:
            print(f"[IPGeoTokenManager] {event}: {kwargs}")

    def log_visitor(self, log_geo=True):
        """Логирует посещение + гео"""
        ip = request.remote_addr
        geo_data = self.get_geo_info(ip) if log_geo else {}
        self._log("visitor", ip=ip, geo=bool(geo_data))
        return ip, geo_data

    def get_geo_info(self, ip):
        """Геоинформация по IP через ipapi.co"""
        try:
            response = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self._log("geo_data", ip=ip, city=data.get("city"), country=data.get("country_name"))
                return data
            else:
                self._log("geo_data_failed", ip=ip, status=response.status_code)
                return {}
        except Exception as e:
            self._log("geo_data_error", ip=ip, error=str(e))
            return {}

    def api_blueprint(self) -> Blueprint:
        """Инициализация класса Blueprint"""
        bp = Blueprint("ipgeo_token_api", __name__)

        @bp.route("/test", methods=["GET"])
        @self.require_api_token
        def test_api():
            ip, geo = self.log_visitor()
            self._log("test_endpoint_called", level="info", ip=ip, geo=geo)
            return (
                jsonify(
                    {"message": "API работает!", "ip": ip, "country": geo.get("country_name"), "city": geo.get("city")}
                ),
                200,
            )

        @bp.route("/reload-tokens", methods=["POST"])
        @self.require_api_token
        def reload_tokens():
            try:
                self.reload_tokens()
                return jsonify({"status": "success", "tokens_count": len(self.allowed_tokens)}), 200
            except Exception as e:
                self._log("token_reload_failed", level="error", error=str(e))
                return jsonify({"status": "error", "message": str(e)}), 500

        return bp

    def load_allowed_tokens(self):
        """Загружает токены из файла (один токен на строку)."""
        if not os.path.exists(self.token_file):
            raise FileNotFoundError(f"Token file not found: {self.token_file}")
        try:
            with open(self.token_file, "r") as f:
                tokens = {line.strip() for line in f if line.strip()}
            self._log("tokens_loaded", count=len(tokens))
            return tokens
        except Exception as e:
            raise RuntimeError(f"Failed to load tokens: {e}") from e

    def reload_tokens(self):
        """Обновляет список токенов без перезапуска."""
        self.allowed_tokens = self.load_allowed_tokens()
        self._log("tokens_reloaded", count=len(self.allowed_tokens))

    def is_valid_token(self, token):
        """Проверка валидности токена."""
        result = token in self.allowed_tokens
        self._log("token_checked", token=token, valid=result, ip=request.remote_addr)
        return result

    def require_api_token(self, f):
        """Flask-декоратор проверки токена."""

        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                self._log("token_missing", ip=request.remote_addr)
                return jsonify({"error": "Missing or invalid token"}), 401

            token = auth.replace("Bearer ", "", 1).strip()
            if not self.is_valid_token(token):
                self._log("token_invalid", token=token, ip=request.remote_addr)
                return jsonify({"error": "Unauthorized"}), 403

            return f(*args, **kwargs)

        return decorated
