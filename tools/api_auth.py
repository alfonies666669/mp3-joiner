import os
import hmac
import ipaddress
from functools import wraps

import requests
from flask import Blueprint, jsonify, request
from requests.adapters import Retry, HTTPAdapter

from logger.logger import user_logger


def _bool(env: str, default: bool) -> bool:
    v = os.getenv(env, str(default)).strip().lower()
    return v in ("1", "true", "yes", "y", "on")


class IPGeoTokenManager:
    """
    Token + optional geolocation helper with safe logging and env-driven behavior.
    """

    def __init__(self, token_file: str | None = None, logger=None):
        self.logger = logger or user_logger
        self.token_file = token_file or os.getenv("TOKEN_FILE_PATH")
        self.tokens_required = _bool("API_TOKENS_REQUIRED", True)
        self.geo_enabled = _bool("GEO_LOOKUP_ENABLED", False)
        self.geo_timeout = float(os.getenv("GEO_TIMEOUT", "3"))
        self.geo_url_tpl = os.getenv("GEO_URL", "https://ipapi.co/{ip}/json/")

        self._tokens_mtime: float | None = None
        self.allowed_tokens: set[str] = set()
        self._http = self._build_http()

        self._init_tokens()

    def _log(self, event: str, level: str = "info", **kwargs):
        """Logging"""
        payload = {"event": event, **kwargs}
        lg = self.logger
        if lg and hasattr(lg, level):
            getattr(lg, level)(event, extra={"extra": payload})
        else:
            print(f"[IPGeoTokenManager] {event}: {kwargs}")

    @staticmethod
    def _build_http() -> requests.Session:
        """HTTP session with retry"""
        s = requests.Session()
        retries = Retry(
            total=2,
            backoff_factor=0.2,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        s.mount("https://", HTTPAdapter(max_retries=retries))
        s.mount("http://", HTTPAdapter(max_retries=retries))
        return s

    # ---------- IP helpers ----------
    @staticmethod
    def _client_ip() -> str:
        """
        Клиентский IP:
        1) X-Forwarded-For (первый адрес)
        2) X-Real-IP
        3) access_route[0] (если ProxyFix/WSGI что-то положили)
        4) REMOTE_ADDR
        """
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first

        xri = request.headers.get("X-Real-IP")
        if xri:
            return xri

        route = getattr(request, "access_route", None) or []
        if route:
            return route[0]

        return request.remote_addr or "0.0.0.0"

    @staticmethod
    def _is_private(ip: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip)
            return addr.is_private or addr.is_loopback or addr.is_reserved
        except ValueError:
            return True

    def _init_tokens(self):
        """Tokens"""
        if self.token_file and os.path.exists(self.token_file):
            self._load_tokens(force=True)
        else:
            if self.tokens_required:
                raise FileNotFoundError(f"Token file not found but API_TOKENS_REQUIRED=true: {self.token_file}")
            self._log("tokens_disabled", level="warning")

    @staticmethod
    def _parse_tokens(text: str) -> set[str]:
        """Tokens parse"""
        tokens = set()
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            tokens.add(line)
        return tokens

    def _load_tokens(self, force: bool = False):
        """Token loads"""
        if not self.token_file:
            return
        try:
            st = os.stat(self.token_file)
            if not force and self._tokens_mtime is not None and st.st_mtime <= self._tokens_mtime:
                return
            with open(self.token_file, encoding="utf-8") as f:
                new_tokens = self._parse_tokens(f.read())
            self.allowed_tokens = new_tokens
            self._tokens_mtime = st.st_mtime
            self._log("tokens_loaded", count=len(new_tokens))
        except Exception as e:
            if self.tokens_required:
                raise RuntimeError(f"Failed to load tokens: {e}") from e
            self._log("tokens_load_failed", level="error", error=str(e))

    def reload_tokens(self):
        """Token reloads"""
        self._load_tokens(force=True)
        self._log("tokens_reloaded", count=len(self.allowed_tokens))

    @staticmethod
    def _extract_bearer() -> str | None:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        return auth.replace("Bearer ", "", 1).strip()

    def is_valid_token(self, token: str | None) -> bool:
        if not self.tokens_required:
            return True  # auth disabled
        if not token:
            return False
        # constant-time checks against the set
        # We can't compare against all in true constant time without hashing.
        # For simplicity, compare exact string using compare_digest over each candidate.
        return any(hmac.compare_digest(t, token) for t in self.allowed_tokens)

    def require_api_token(self, f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            token = None
            if auth.startswith("Bearer "):
                token = auth.replace("Bearer ", "", 1).strip()
            if token is None:
                ip = self._client_ip()
                self._log("auth_missing", level="warning", ip=ip)
                return jsonify({"error": "Missing bearer token"}), 401
            if not self.is_valid_token(token):
                ip = self._client_ip()
                self._log("auth_invalid", level="warning", ip=ip, has_token=True)
                return jsonify({"error": "Forbidden"}), 403
            return f(*args, **kwargs)

        return decorated

    # ---------- Geo ----------
    def get_geo_info(self, ip: str) -> dict:
        if not self.geo_enabled:
            return {}
        if self._is_private(ip):
            return {}
        url = self.geo_url_tpl.format(ip=ip)
        try:
            resp = self._http.get(url, timeout=self.geo_timeout)
            if resp.status_code == 200:
                data = resp.json()
                self._log("geo_ok", ip=ip, city=data.get("city"), country=data.get("country_name"))
                return data
            self._log("geo_http_fail", ip=ip, status=resp.status_code)
        except Exception as e:
            self._log("geo_error", ip=ip, error=str(e))
        return {}

    def log_visitor(self, log_geo: bool = True) -> tuple[str, dict]:
        ip = self._client_ip()
        geo = self.get_geo_info(ip) if log_geo else {}
        self._log("visitor", ip=ip, geo=bool(geo))
        return ip, geo

    # ---------- Blueprint ----------
    def api_blueprint(self) -> Blueprint:
        bp = Blueprint("ipgeo_token_api", __name__)

        @bp.route("/health", methods=["GET"])
        def health():
            return (
                jsonify(
                    {
                        "status": "ok",
                        "tokens_required": self.tokens_required,
                        "tokens_loaded": len(self.allowed_tokens),
                        "geo_enabled": self.geo_enabled,
                    }
                ),
                200,
            )

        @bp.route("/test", methods=["GET"])
        @self.require_api_token
        def test_api():
            ip, geo = self.log_visitor(log_geo=True)
            return (
                jsonify(
                    {
                        "message": "API OK",
                        "ip": ip,
                        "country": geo.get("country_name"),
                        "city": geo.get("city"),
                    }
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
                return jsonify({"status": "error", "message": "reload failed"}), 500

        return bp
