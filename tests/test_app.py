"""Интеграционные тесты Flask-приложения: healthz, index, /merge и обработчик 413."""

import io
import os
import zipfile
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

import app as app_module

from tools.http import handle_413


def _origin_headers() -> dict[str, str]:
    """Заголовок Origin, имитирующий same-origin запрос с localhost."""
    return {"Origin": "http://localhost"}


def test_healthz_ok(client):
    """GET /healthz — здоров, отдает базовую информацию."""
    r = client.get("/healthz")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"
    assert "ffmpeg" in data
    assert "max_files" in data
    assert "max_per_file_mb" in data


def test_index_sets_csrf_and_renders(client):
    """GET / — в сессии появляется csrf_token, страница рендерится."""
    r = client.get("/")
    assert r.status_code == 200
    with client.session_transaction() as sess:
        assert "csrf_token" in sess


def test_merge_400_no_files(client):
    """POST /merge без файлов → 400 и сообщение об ошибке."""
    with client.session_transaction() as sess:
        sess["csrf_token"] = "test-csrf"

    resp = client.post(
        "/merge",
        data={"count": "2", "csrf_token": "test-csrf"},
        headers=_origin_headers(),
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "No files provided"


def test_merge_429_rate_limited(client):
    """POST /merge при срабатывании rate-limit → 429."""
    old_check = app_module.limiter.check
    app_module.limiter.check = lambda: False
    try:
        with client.session_transaction() as sess:
            sess["csrf_token"] = "test-csrf"

        resp = client.post(
            "/merge",
            data={"count": "2", "csrf_token": "test-csrf"},
            headers=_origin_headers(),
            content_type="multipart/form-data",
        )
        assert resp.status_code == 429
        assert resp.get_json()["error"] == "Too many requests"
    finally:
        app_module.limiter.check = old_check


def test_merge_happy_path_minimal_pipeline(client, tmp_path):  # pylint: disable=unused-argument
    """Полный happy-path /merge с моками валидации, мерджа и zip-а."""
    with client.session_transaction() as sess:
        sess["csrf_token"] = "test-csrf"

    # in-memory «mp3»
    f1 = io.BytesIO(b"ID3\x00\x00\x00aaaa")
    f2 = io.BytesIO(b"ID3\x00\x00\x00bbbb")

    def fake_validate(_req, _max_files, _max_mb, _ffmpeg_ok, _check_fn) -> tuple:
        """Мокаем validate_merge_request: отдаем 2 FileStorage и успех."""
        return (
            [
                FileStorage(stream=f1, filename="1.mp3", content_type="audio/mpeg"),
                FileStorage(stream=f2, filename="2.mp3", content_type="audio/mpeg"),
            ],
            2,
            None,
            None,
        )

    def fake_merge(_file_paths, _count, merged_folder):
        """Мокаем smart_merge_mp3_files: создаем один «мерджнутый» mp3."""
        out1 = os.path.join(merged_folder, "merged_1.mp3")
        with open(out1, "wb") as f:
            f.write(b"merged")
        return [out1]

    def fake_zip(merged_folder, merged_files):
        """Мокаем create_zip: создаем реальный zip с переданными файлами."""
        zip_path = os.path.join(merged_folder, "merged_files.zip")
        with zipfile.ZipFile(zip_path, "w") as z:
            for p in merged_files:
                z.write(p, arcname=os.path.basename(p))
        return zip_path

    with (
        patch("app.validate_merge_request", side_effect=fake_validate),
        patch("app.smart_merge_mp3_files", side_effect=fake_merge),
        patch("app.create_zip", side_effect=fake_zip),
    ):
        data = {
            "count": "2",
            "csrf_token": "test-csrf",
            "files": [
                (io.BytesIO(b"ID3a"), "1.mp3", "audio/mpeg"),
                (io.BytesIO(b"ID3b"), "2.mp3", "audio/mpeg"),
            ],
        }

        resp = client.post("/merge", data=data, headers=_origin_headers())

        if resp.status_code != 200:
            # Удобно печатать ответ при падении
            print("Body:\n", resp.get_data(as_text=True))

        assert resp.status_code == 200
        assert resp.headers.get("Content-Type", "").startswith("application/zip")
        assert resp.headers.get("X-Process-Time") is not None
        assert len(resp.data) > 0


def test_merge_413_error_handler():
    """Проверяем зарегистрированный error handler 413 — формирует корректный JSON."""
    with app_module.app.app_context():
        handler = handle_413(app_module.MAX_CONTENT_LENGTH)
        resp = handler(None)
        data, status = resp
        assert status == 413
        payload = data.get_json()
        assert "The total upload is too large" in payload["error"]
        assert str(int(app_module.MAX_CONTENT_LENGTH / (1024 * 1024))) in payload["error"]
