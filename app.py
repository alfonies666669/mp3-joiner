"""Flask-приложение для объединения MP3: маршруты, конфиг, и склейка через utils."""

import os
import time
import shutil
import tempfile

from flask_compress import Compress
from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Flask, Response, jsonify, request, session, send_file, render_template, after_this_request

from app_version import __version__

from logger.logger import app_logger, user_logger

from tools.http import handle_413
from tools.system import ffmpeg_ok
from tools.limits import RateLimiter
from tools.api_auth import IPGeoTokenManager
from tools.validation import validate_merge_request
from tools.security import ensure_csrf, auth_bearer_or_same_origin_csrf
from tools.utils import create_zip, saving_files, check_files_are_mp3, smart_merge_mp3_files

app = Flask(__name__)
Compress(app)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# ---- Config / constants ----
MAX_FILES = int(os.getenv("MAX_FILES", "50"))
MAX_PER_FILE_MB = int(os.getenv("MAX_PER_FILE_MB", "50"))
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(100 * 1024 * 1024)))
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

TOKEN_FILE_PATH = os.getenv("TOKEN_FILE_PATH", "allowed_tokens.txt")
app.secret_key = os.getenv("SECRET_KEY", "dev-insecure-change-me")
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN")

RATE_LIMIT_WINDOW_SEC = int(os.getenv("RATE_LIMIT_WINDOW_SEC", "60"))
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "20"))

# ---- Extensions / helpers ----
try:
    TOKEN_MANAGER = IPGeoTokenManager(token_file=TOKEN_FILE_PATH, logger=user_logger)
    app.register_blueprint(TOKEN_MANAGER.api_blueprint(), url_prefix="/api")
except Exception as err:
    TOKEN_MANAGER = None
    app_logger.warning("Token API disabled: %s", err)

limiter = RateLimiter(RATE_LIMIT_WINDOW_SEC, RATE_LIMIT_MAX_REQUESTS)
FFMPEG_AVAILABLE = ffmpeg_ok()

# ---- Errors ----
app.register_error_handler(413, handle_413(MAX_CONTENT_LENGTH))


# ---- Routes ----
@app.route("/healthz", methods=["GET"])
def healthz():
    """Healthcheck: ffmpeg/лимиты/конфиг."""
    return (
        jsonify(
            {
                "status": "ok",
                "ffmpeg": FFMPEG_AVAILABLE,
                "max_content_length_mb": int(round(MAX_CONTENT_LENGTH / (1024 * 1024), 2)),
                "max_files": MAX_FILES,
                "max_per_file_mb": MAX_PER_FILE_MB,
                "version": __version__,
            }
        ),
        200,
    )


@app.route("/")
def index():
    """
    Главная страница приложения.
    Возвращает HTML-шаблон главной страницы.
    """
    ensure_csrf()
    ip = request.remote_addr
    if user_logger:
        user_logger.info("Visited /", extra={"extra": {"ip": ip, "status": "visited", "type": "pageview"}})
    else:
        app_logger.warning("user_logger не инициализирован — проверь USER_LOG_PATH")
    return render_template("index.html", csrf_token=session["csrf_token"], version=__version__)


@app.route("/how-it-works")
def how_it_works():
    """
    Страница "Как это работает".
    Возвращает HTML-шаблон страницы с описанием работы сервиса.
    """
    ensure_csrf()
    return render_template("how-it-works.html", csrf_token=session["csrf_token"])


@app.route("/merge", methods=["POST"])
@auth_bearer_or_same_origin_csrf(TOKEN_MANAGER, ALLOWED_ORIGIN)
def merge_files():  # pylint: disable=too-many-locals
    """POST /merge: принимает файлы, склеивает группами и отдаёт zip."""
    start_time = time.time()

    if not limiter.check():
        return jsonify({"error": "Too many requests"}), 429

    files, count, error_resp, error_code = validate_merge_request(
        request, MAX_FILES, MAX_PER_FILE_MB, FFMPEG_AVAILABLE, check_files_are_mp3
    )
    if error_resp is not None:
        return error_resp, error_code

    ip_addr = request.remote_addr or "unknown"

    try:
        upload_folder = tempfile.mkdtemp(prefix="mp3_up_")
        merged_folder = tempfile.mkdtemp(prefix="mp3_merged_")

        file_paths = saving_files(upload_folder, files)

        max_bytes = MAX_PER_FILE_MB * 1024 * 1024
        for p in file_paths:
            if os.path.getsize(p) > max_bytes:
                shutil.rmtree(upload_folder, ignore_errors=True)
                shutil.rmtree(merged_folder, ignore_errors=True)
                return jsonify({"error": f"File too large: {os.path.basename(p)} (> {MAX_PER_FILE_MB} MB)"}), 400

        merged_files = smart_merge_mp3_files(file_paths, count, merged_folder=merged_folder)
        archive_path = create_zip(merged_folder, merged_files)

        duration = round(time.time() - start_time, 3)
        app_logger.info("Files merged successfully in %ss", duration)
        if user_logger:
            user_logger.info(
                "MP3 merge success",
                extra={
                    "extra": {
                        "ip": ip_addr,
                        "files": len(files),
                        "group_size": count,
                        "duration_sec": duration,
                        "status": "success",
                    }
                },
            )

        @after_this_request
        def cleanup(response: Response):
            for path in (upload_folder, merged_folder):
                try:
                    shutil.rmtree(path)
                except OSError as e:
                    app_logger.error("Error cleaning temp dir %s: %s", path, e)
            response.headers["X-Process-Time"] = str(duration)
            response.headers["Cache-Control"] = "no-store"
            return response

        return send_file(archive_path, as_attachment=True, download_name="merged_files.zip", mimetype="application/zip")

    except Exception as err:
        app_logger.error("Error during merging files: %s", err)
        if user_logger:
            user_logger.error(
                "MP3 merge fail",
                extra={"extra": {"ip": ip_addr, "files": len(files), "status": "fail", "reason": str(err)}},
            )
        return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app_logger.info("Starting mp3-joiner %s", __version__)
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=True)
