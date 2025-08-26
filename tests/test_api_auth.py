"""Тесты для IPGeoTokenManager"""

# pylint: disable=protected-access, unused-argument, redefined-outer-name

from types import SimpleNamespace

import pytest
from flask import Flask

from tools.api_auth import IPGeoTokenManager

# ---------- фикстуры ----------


@pytest.fixture()
def token_file(tmp_path):
    """Создаёт временный файл токенов с парой валидных значений."""
    p = tmp_path / "allowed_tokens.txt"
    p.write_text("# comment\n\nGOOD_TOKEN\nANOTHER\n", encoding="utf-8")
    return str(p)


@pytest.fixture()
def mgr(token_file, monkeypatch):
    """Инициализирует менеджер токенов с включённой проверкой токенов и выключенной геолокацией."""
    monkeypatch.setenv("API_TOKENS_REQUIRED", "true")
    monkeypatch.setenv("GEO_LOOKUP_ENABLED", "false")
    return IPGeoTokenManager(token_file=token_file, logger=None)


@pytest.fixture()
def app_with_bp(mgr):
    """Flask-приложение с зарегистрированным Blueprint-ом менеджера токенов."""
    app = Flask(__name__)
    app.testing = True
    app.register_blueprint(mgr.api_blueprint(), url_prefix="/api")
    return app


@pytest.fixture()
def client(app_with_bp):
    """Тестовый клиент Flask для запросов к /api/*."""
    return app_with_bp.test_client()


# ---------- unit: парсинг и токены ----------


def test_parse_tokens_trims_and_ignores_comments(mgr):
    """Проверка распаковки токенов"""
    text = " \n# a\nTOKEN1 \nTOKEN2\n# b\n"
    out = mgr._parse_tokens(text)
    assert out == {"TOKEN1", "TOKEN2"}


def test_init_loads_tokens_from_file(mgr):
    """Проверка загрузки токенов из файла"""
    assert "GOOD_TOKEN" in mgr.allowed_tokens
    assert "ANOTHER" in mgr.allowed_tokens


def test_is_valid_token_enabled(mgr):
    """Проверка валидности токенов"""
    assert mgr.is_valid_token("GOOD_TOKEN") is True
    assert mgr.is_valid_token("BAD") is False
    assert mgr.is_valid_token(None) is False


def test_is_valid_token_disabled(token_file, monkeypatch):
    """Проверка невалидности токенов"""
    monkeypatch.setenv("API_TOKENS_REQUIRED", "false")
    m = IPGeoTokenManager(token_file=token_file, logger=None)
    assert m.is_valid_token(None) is True
    assert m.is_valid_token("whatever") is True


def test_reload_tokens_rereads_file(mgr):
    """Проверка перезаписи токенов"""
    with open(mgr.token_file, "w", encoding="utf-8") as f:
        f.write("NEW1\nNEW2\n")
    mgr.reload_tokens()
    assert mgr.allowed_tokens == {"NEW1", "NEW2"}


# ---------- unit: IP helpers ----------


@pytest.mark.parametrize(
    "headers,remote_addr,expected",
    [
        ({"X-Forwarded-For": "203.0.113.10, 10.0.0.1"}, "127.0.0.1", "203.0.113.10"),
        ({"X-Real-IP": "198.51.100.5"}, "127.0.0.1", "198.51.100.5"),
        ({}, "192.0.2.9", "192.0.2.9"),
    ],
)
def test_client_ip(mgr, headers, remote_addr, expected):
    """Проверка client ip"""
    app = Flask(__name__)
    with app.test_request_context("/", headers=headers, environ_base={"REMOTE_ADDR": remote_addr}):
        assert mgr._client_ip() == expected


@pytest.mark.parametrize(
    "ip,is_private",
    [
        ("127.0.0.1", True),
        ("10.0.0.7", True),
        ("192.168.1.2", True),
        ("203.0.113.10", True),  # TEST-NET-3 помечаем как непубличный для наших целей
        ("8.8.8.8", False),
    ],
)
def test_is_private(mgr, ip, is_private):
    """Проверка приватности"""
    assert mgr._is_private(ip) is is_private


# ---------- unit: geo ----------


def test_get_geo_info_disabled_returns_empty(mgr):
    """Гео пуст"""
    mgr.geo_enabled = False
    assert mgr.get_geo_info("203.0.113.10") == {}


def test_get_geo_info_private_ip_skipped(mgr):
    """Гео не пуст"""
    mgr.geo_enabled = True
    assert mgr.get_geo_info("127.0.0.1") == {}


def test_get_geo_info_ok_http_mock(mgr, monkeypatch):
    """Проверка Гео True"""
    mgr.geo_enabled = True
    fake_resp = SimpleNamespace(
        status_code=200,
        json=lambda: {"city": "Berlin", "country_name": "Germany"},
    )
    mgr._http = SimpleNamespace(get=lambda url, timeout: fake_resp)

    # Публичный IP, не private/reserved
    data = mgr.get_geo_info("8.8.8.8")
    assert data.get("city") == "Berlin"
    assert data.get("country_name") == "Germany"


# ---------- интеграция: декоратор require_api_token ----------


def test_require_api_token_missing(mgr):
    """Проверка апи токен отсутствует"""
    app = Flask(__name__)
    app.testing = True

    @app.route("/secret")
    @mgr.require_api_token
    def secret():
        return "ok"

    c = app.test_client()
    r = c.get("/secret")
    assert r.status_code == 401
    assert r.get_json()["error"].lower().startswith("missing")


def test_require_api_token_invalid(mgr):
    """Проверка апи токен не верный"""
    app = Flask(__name__)
    app.testing = True

    @app.route("/secret")
    @mgr.require_api_token
    def secret():
        return "ok"

    c = app.test_client()
    r = c.get("/secret", headers={"Authorization": "Bearer WRONG"})
    assert r.status_code == 403
    assert r.get_json()["error"] == "Forbidden"


def test_require_api_token_ok(mgr):
    """Проверка апи токен верный"""
    app = Flask(__name__)
    app.testing = True

    @app.route("/secret")
    @mgr.require_api_token
    def secret():
        return "ok"

    c = app.test_client()
    r = c.get("/secret", headers={"Authorization": "Bearer GOOD_TOKEN"})
    assert r.status_code == 200
    assert r.data == b"ok"


# ---------- интеграция: blueprint ----------


def test_blueprint_health(client, mgr):
    """Проверка blueprint"""
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.get_json()
    assert set(data) >= {"status", "tokens_required", "tokens_loaded", "geo_enabled"}


def test_blueprint_test_requires_token(client):
    """Проверка blueprint tokens"""
    # без токена — 401
    r = client.get("/api/test")
    assert r.status_code == 401
    # с токеном — 200, и структура ответа ожидаемая
    r = client.get("/api/test", headers={"Authorization": "Bearer GOOD_TOKEN"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["message"] == "API OK"
    assert "ip" in data  # ip/geo могут быть пустыми — проверяем ключи


def test_blueprint_reload_tokens(client, mgr):
    """Проверка перезагрузки токенов"""
    # Перепишем файл токенов и вызовем endpoint
    with open(mgr.token_file, "w", encoding="utf-8") as f:
        f.write("NEW_A\nNEW_B\n")
    r = client.post("/api/reload-tokens", headers={"Authorization": "Bearer GOOD_TOKEN"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "success"
    assert data["tokens_count"] == 2
