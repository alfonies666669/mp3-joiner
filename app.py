"""
Main Flask application for merging MP3 files.
"""

import os
import shutil
import tempfile
from typing import Any, List

from flask_compress import Compress
from flask import Flask, jsonify, request, send_file, render_template, after_this_request

from tools.utils import logger, create_zip, saving_files, merge_mp3_files_ffmpeg

app = Flask(__name__)
Compress(app)

# Получаем максимальный размер загружаемых файлов из переменной окружения
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "104857600"))  # 100 MB
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


@app.route("/")
def index():
    """
    Главная страница приложения.

    Возвращает HTML-шаблон главной страницы.
    """
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
    logger.error("Request entity too large")
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
    files = request.files.getlist("files")  # type: List[Any]
    count = request.form.get("count", type=int)

    if not files or count is None:
        error_msg = "Files or count not provided"
        logger.error("Files or count not provided")
        return jsonify({"error": error_msg}), 400

    for file in files:
        if file.mimetype != "audio/mpeg":
            logger.error("Invalid file type: %s", file.filename)
            return jsonify({"error": "Only MP3 files are allowed"}), 400

    try:
        upload_folder = tempfile.mkdtemp()
        merged_folder = tempfile.mkdtemp()

        file_paths = saving_files(upload_folder, files)
        merged_files = merge_mp3_files_ffmpeg(file_paths, count, merged_folder=merged_folder)
        archive_path = create_zip(merged_folder, merged_files)
        logger.info("Files merged successfully")

        @after_this_request
        def cleanup(response):
            try:
                shutil.rmtree(upload_folder)
                shutil.rmtree(merged_folder)
            except OSError as E:
                logger.error("Error during cleanup: %s", E)
            return response

        return send_file(archive_path, as_attachment=True)

    except Exception as E:
        logger.error("Error during merging files: %s", E)
        return jsonify({"error": str(E)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=True)
