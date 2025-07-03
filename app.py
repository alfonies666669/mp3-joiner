"""
Main Flask application for merging MP3 files.
"""

import os
import shutil
import tempfile
from typing import Any, List

from flask_compress import Compress
from flask import Flask, jsonify, request, send_file, render_template, after_this_request

from tools.utils import logger, create_zip, saving_files, check_files_are_mp3, smart_merge_mp3_files

app = Flask(__name__)
Compress(app)

# Получаем максимальный размер загружаемых файлов из переменной окружения
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 100 * 1024 * 1024))
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

    error = check_files_are_mp3(files)
    if error:
        return jsonify(error[0]), error[1]

    try:
        upload_folder = tempfile.mkdtemp()
        merged_folder = tempfile.mkdtemp()

        file_paths = saving_files(upload_folder, files)
        merged_files = smart_merge_mp3_files(file_paths, count, merged_folder=merged_folder)
        archive_path = create_zip(merged_folder, merged_files)
        logger.info("Files merged successfully")

        @after_this_request
        def cleanup(response):
            try:
                shutil.rmtree(upload_folder)
            except OSError as e:
                logger.error("Error cleaning upload_folder: %s", e)
            try:
                shutil.rmtree(merged_folder)
            except OSError as e:
                logger.error("Error cleaning merged_folder: %s", e)
            return response

        return send_file(archive_path, as_attachment=True)

    except Exception as E:
        logger.error("Error during merging files: %s", E)
        return jsonify({"error": str(E)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=True)
