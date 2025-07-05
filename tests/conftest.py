import io
import zipfile
from contextlib import contextmanager
from os import path, environ, makedirs

import pytest

environ.setdefault("SECRET_KEY", "test-secret")
environ.setdefault("ALLOWED_ORIGIN", "http://localhost")
environ.setdefault("API_TOKENS_REQUIRED", "false")

import app as app_module  # noqa: E402


@pytest.fixture(scope="session")
def app():
    app_module.FFMPEG_AVAILABLE = True
    app_module.limiter.check = lambda: True
    app_module.app.testing = True
    return app_module.app


@pytest.fixture()
def client(app):
    return app.test_client()


@contextmanager
def csrf_session(client):
    """Устанавливает csrf_token в сессию и возвращает его значение."""
    with client.session_transaction() as sess:
        sess["csrf_token"] = "test-csrf"
    yield "test-csrf"


def make_mp3_filestorage(name="a.mp3", payload=b"ID3\x03\x00\x00TEST"):
    """
    Создаём in-memory FileStorage, похожий на mp3.
    validate_merge_request мы замокаем, но saving_files потребует FileStorage.save().
    """
    return name, [io.BytesIO(payload), name, "audio/mpeg"]


def build_zip_with_files(tmp_dir, filenames):
    """Создаёт ZIP с пустыми файлами указанными именами и возвращает путь."""
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
