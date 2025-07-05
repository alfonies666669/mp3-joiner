import io
from types import SimpleNamespace

import pytest
from flask import Flask, request
from werkzeug.datastructures import FileStorage

from tools.validation import _check_sizes, _check_content_type, _check_files_and_count, validate_merge_request


# ---------- helpers ----------
def _file_part(name: str, payload: bytes = b"ID3\x00\x00\x00aaaa") -> tuple[io.BytesIO, str]:
    """Возвращает кортеж для multipart: (stream, filename)."""
    return io.BytesIO(payload), name


def _fs(name: str, payload: bytes = b"ID3\x00\x00\x00aaaa") -> FileStorage:
    """Явно создаём FileStorage (для юнит-тестов приватных проверок)."""
    return FileStorage(stream=io.BytesIO(payload), filename=name, content_type="audio/mpeg")


# ---------- unit-тесты приватных чеков ----------
def test__check_content_type_ok():
    app = Flask(__name__)
    with app.test_request_context("/", method="POST", content_type="multipart/form-data"):
        msg, code = _check_content_type(request)
        assert msg is None and code == 400


def test__check_content_type_fail():
    app = Flask(__name__)
    with app.test_request_context("/", method="POST", content_type="application/json"):
        msg, code = _check_content_type(request)
        assert msg == "Content-Type must be multipart/form-data"
        assert code == 415


@pytest.mark.parametrize(
    "files,count,max_files,expect_msg",
    [
        ([], 1, 5, "No files provided"),
        ([_fs("a.mp3")], None, 5, "Parameter 'count' is required and must be integer"),
        ([_fs("a.mp3")], 0, 5, "Parameter 'count' must be > 0"),
        ([_fs("a.mp3"), _fs("b.mp3"), _fs("c.mp3")], 1, 2, "Too many files (>2). Reduce the number of files."),
        ([_fs("a.mp3")], 2, 5, "Parameter 'count' must be <= number of files"),
    ],
)
def test__check_files_and_count_errors(files, count, max_files, expect_msg):
    msg, code = _check_files_and_count(files, count, max_files)
    assert msg == expect_msg and code == 400


def test__check_files_and_count_ok():
    msg, code = _check_files_and_count([_fs("a.mp3"), _fs("b.mp3")], 2, 5)
    assert msg is None and code == 400


def test__check_sizes_too_large():
    f_big = SimpleNamespace(filename="big.mp3", content_length=51 * 1024 * 1024)
    msg, code = _check_sizes([f_big], 50 * 1024 * 1024)
    assert "too large" in msg and code == 400


def test__check_sizes_ok():
    f = _fs("a.mp3")
    msg, code = _check_sizes([f], 50 * 1024 * 1024)
    assert msg is None and code == 400


# ---------- интеграционные тесты validate_merge_request ----------
def test_validate_wrong_mimetype():
    app = Flask(__name__)
    with app.test_request_context("/", method="POST", content_type="text/plain"):
        files, count, err, status = validate_merge_request(
            request, max_files=5, max_per_file_mb=50, ffmpeg_available=True, check_files_are_mp3_fn=lambda _: None
        )
        assert files is None and count is None
        assert err is not None and status == 415
        assert err.get_json()["error"].startswith("Content-Type")


def test_validate_no_files():
    app = Flask(__name__)
    with app.test_request_context("/", method="POST", data={"count": "2"}, content_type="multipart/form-data"):
        files, count, err, status = validate_merge_request(request, 5, 50, True, lambda _: None)
        assert err is not None and status == 400
        assert err.get_json()["error"] == "No files provided"


def test_validate_count_missing():
    app = Flask(__name__)
    with app.test_request_context(
        "/", method="POST", data={"files": [_file_part("a.mp3")]}, content_type="multipart/form-data"
    ):
        files, count, err, status = validate_merge_request(request, 5, 50, True, lambda _: None)
        assert err is not None and status == 400
        assert "required" in err.get_json()["error"]


def test_validate_ffmpeg_unavailable():
    app = Flask(__name__)
    with app.test_request_context(
        "/",
        method="POST",
        data={"count": "1", "files": [_file_part("a.mp3")]},
        content_type="multipart/form-data",
    ):
        files, count, err, status = validate_merge_request(request, 5, 50, False, lambda _: None)
        assert err is not None and status == 500
        assert "FFmpeg" in err.get_json()["error"]


def test_validate_mp3_error_bubbled():
    app = Flask(__name__)
    with app.test_request_context(
        "/",
        method="POST",
        data={"count": "1", "files": [_file_part("a.mp3")]},
        content_type="multipart/form-data",
    ):

        def fake_check(_files):
            return {"error": "File a.mp3 is not a valid MP3"}, 400

        files, count, err, status = validate_merge_request(request, 5, 50, True, fake_check)
        assert files is None and count is None
        assert status == 400
        assert err.get_json()["error"].endswith("valid MP3")


def test_validate_ok_path():
    app = Flask(__name__)
    with app.test_request_context(
        "/",
        method="POST",
        data={
            "count": "2",
            "files": [_file_part("a.mp3"), _file_part("b.mp3")],
        },
        content_type="multipart/form-data",
    ):
        files, count, err, status = validate_merge_request(request, 5, 50, True, lambda _: None)
        assert err is None and status is None
        assert isinstance(files, list) and len(files) == 2
        assert count == 2
