"""Фикстуры и утилиты для тестов веб-приложения."""

from __future__ import annotations

import io
import zipfile
from contextlib import contextmanager
from os import path, environ, makedirs

import pytest

# ВАЖНО: эти переменные должны быть установлены до импорта приложения.
environ.setdefault("SECRET_KEY", "test-secret")
environ.setdefault("ALLOWED_ORIGIN", "http://localhost")
environ.setdefault("API_TOKENS_REQUIRED", "false")

import app as app_module  # pylint: disable=wrong-import-position


@pytest.fixture(scope="session")
def flask_app():
    """Готовит Flask app для тестов: включает testing, отключает лимитер и ffmpeg-проверку."""
    app_module.FFMPEG_AVAILABLE = True
    app_module.limiter.check = lambda: True  # no rate-limit в тестах
    app_module.app.testing = True
    return app_module.app


@pytest.fixture()
def client(flask_app):  # pylint: disable=redefined-outer-name
    """Возвращает тестовый клиент Flask для каждого теста."""
    return flask_app.test_client()


@contextmanager
def csrf_session(client):  # pylint: disable=redefined-outer-name
    """Устанавливает csrf_token в сессию клиента и отдаёт его значение в менеджере контекста."""
    with client.session_transaction() as sess:
        sess["csrf_token"] = "test-csrf"
    yield "test-csrf"


def make_mp3_filestorage(name: str = "a.mp3", payload: bytes = b"ID3\x03\x00\x00TEST"):
    """
    Создаёт кортеж для поля формы с in-memory «mp3».
    Формат: (fieldname, [stream, filename, content_type]) — совместим с werkzeug тестовым клиентом.
    """
    return name, [io.BytesIO(payload), name, "audio/mpeg"]


def build_zip_with_files(tmp_dir: str, filenames: list[str]) -> str:
    """Создаёт ZIP в tmp_dir с пустыми файлами filenames и возвращает путь к архиву."""
    for fn in filenames:
        p = path.join(tmp_dir, fn)
        makedirs(path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(b"data")
    zip_path = path.join(tmp_dir, "merged_files.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        for fn in filenames:
            zf.write(path.join(tmp_dir, fn), arcname=fn)
    return zip_path
