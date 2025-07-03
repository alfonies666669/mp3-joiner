"""
Main Flask application for merging MP3 files.
"""

import os
import time
import shutil
import tempfile
from typing import Any, List

from flask_compress import Compress
from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Flask, jsonify, request, send_file, render_template, after_this_request

from logger.logger import app_logger, user_logger
from tools.utils import create_zip, saving_files, check_files_are_mp3, smart_merge_mp3_files

app = Flask(__name__)
Compress(app)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# Получаем максимальный размер загружаемых файлов из переменной окружения
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(100 * 1024 * 1024)))
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


@app.route("/")
def index():
    """
    Главная страница приложения.

    Возвращает HTML-шаблон главной страницы.
    """
    ip = request.remote_addr
    user_logger.info("Visited /", extra={"extra": {"ip": ip, "status": "visited", "type": "pageview"}})
    return render_template("index.html")


@app.route("/how-it-works")
def how_it_works():
    """
    Страница "Как это работает".

    Возвращает HTML-шаблон страницы с описанием работы сервиса.
    """
    return render_template("how-it-works.html")


@app.errorhandler(413)
def request_entity_too_large(_):
    """
    Обработчик ошибки превышения размера запроса (HTTP 413).

    :param _: Неиспользуемый аргумент ошибки
    :return: JSON-ответ с сообщением об ошибке
    """
    app_logger.error("Request entity too large")
    return (
        jsonify(
            {
                "error": f"The total file size is too large (> {MAX_CONTENT_LENGTH / (1024 * 1024)} MB). "
                "Please reduce the number of files or their sizes."
            }
        ),
        413,
    )


@app.route("/merge", methods=["POST"])
def merge_files():
    """
    Объединяет загруженные MP3-файлы в группы и возвращает ZIP-архив.

    :return: ZIP-файл с объединёнными файлами или JSON-ошибка
    """
    start_time = time.time()
    print("user_logger:", user_logger)
    files = request.files.getlist("files")  # type: List[Any]
    count = request.form.get("count", type=int)
    ip_addr = request.remote_addr

    if not files or count is None:
        error_msg = "Files or count not provided"
        app_logger.error(error_msg)
        if user_logger:
            user_logger.warning(
                "No files or count",
                extra={
                    "extra": {
                        "ip": ip_addr,
                        "files": len(files) if files else 0,
                        "count": count,
                        "status": "fail",
                        "reason": "missing files/count",
                    }
                },
            )
        return jsonify({"error": error_msg}), 400

    error = check_files_are_mp3(files)
    if error:
        if user_logger:
            user_logger.warning(
                "Invalid MP3 upload",
                extra={"extra": {"ip": ip_addr, "files": len(files), "status": "fail", "reason": "invalid mp3"}},
            )
        return jsonify(error[0]), error[1]

    try:
        upload_folder = tempfile.mkdtemp()
        merged_folder = tempfile.mkdtemp()

        file_paths = saving_files(upload_folder, files)
        merged_files = smart_merge_mp3_files(file_paths, count, merged_folder=merged_folder)
        archive_path = create_zip(merged_folder, merged_files)
        duration = round(time.time() - start_time, 2)
        app_logger.info("Files merged successfully")
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
        def cleanup(response):
            try:
                shutil.rmtree(upload_folder)
            except OSError as e:
                app_logger.error("Error cleaning upload_folder: %s", e)
            try:
                shutil.rmtree(merged_folder)
            except OSError as e:
                app_logger.error("Error cleaning merged_folder: %s", e)
            return response

        return send_file(archive_path, as_attachment=True)

    except Exception as E:
        app_logger.error("Error during merging files: %s", E)
        if user_logger:
            user_logger.error(
                "MP3 merge fail",
                extra={"extra": {"ip": ip_addr, "files": len(files), "status": "fail", "reason": str(E)}},
            )
        return jsonify({"error": str(E)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=True)
