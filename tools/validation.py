"""Валидация входного запроса для эндпоинта /merge.

Модуль разбивает проверки на мелкие функции:
- _check_content_type: корректность Content-Type;
- _check_files_and_count: наличие файлов и валидность параметра count;
- _check_sizes: ограничение на размер каждого файла;
- validate_merge_request: координирует все проверки и формирует единый результат.
"""

import os
from typing import Any, NamedTuple
from collections.abc import Iterable

from flask import Request, Response, jsonify
from werkzeug.datastructures import FileStorage


class ValidationResult(NamedTuple):
    """Результат валидации запроса на мердж.

    Attributes:
        files: Список файлов (FileStorage) при успешной валидации, иначе None.
        count: Величина группировки файлов при успешной валидации, иначе None.
        error_response: Готовый Flask-ответ с ошибкой (jsonify), если валидация не прошла.
        status_code: HTTP-код для error_response или None при успехе.
    """

    files: list[Any] | None
    count: int | None
    error_response: Response | None
    status_code: int | None


def _filter_empty_files(files: Iterable[Any]) -> list[FileStorage]:
    """
    Оставляем только реальные файлы с непустым именем.
    Содержимое (длина) здесь не проверяем – это делается
    дальше в validate_merge_request в «Size check».
    """
    filtered: list[FileStorage] = []
    for f in files:
        if not f:
            continue
        name = getattr(f, "filename", "").strip()
        if name:
            filtered.append(f)
    return filtered


def _check_content_type(req: Request) -> tuple[str | None, int]:
    """Проверяет, что запрос отправлен как multipart/form-data.

    :return: (сообщение_об_ошибке | None, http_код). Если всё ок — (None, 400).
    """
    if req.mimetype != "multipart/form-data":
        return "Content-Type must be multipart/form-data", 415
    return None, 400


def _check_files_and_count(files: list[Any], count: int | None, max_files: int) -> tuple[str | None, int]:
    """Проверяет список файлов и параметр count.

    Проверки:
      - наличие файлов;
      - наличие и валидность count (> 0);
      - лимит на количество файлов;
      - count <= len(files).

    :return: (сообщение_об_ошибке | None, http_код). Если всё ок — (None, 400).
    """
    if not files:
        return "No files provided", 400
    if count is None:
        return "Parameter 'count' is required and must be integer", 400
    if count <= 0:
        return "Parameter 'count' must be > 0", 400
    if len(files) > max_files:
        return f"Too many files (>{max_files}). Reduce the number of files.", 400
    if count > len(files):
        return "Parameter 'count' must be <= number of files", 400
    return None, 400


def _check_sizes(files: list[Any], max_bytes: int) -> tuple[str, int] | tuple[None, None]:
    """Проверяет, что каждый файл не превышает заданный размер.

    :param files: Список объектов FileStorage.
    :param max_bytes: Максимально допустимый размер одного файла в байтах.
    :return: (сообщение_об_ошибке | None, http_код). Если всё ок — (None, 400).
    """
    too_large = next((f for f in files if _file_size(f) > max_bytes), None)
    if too_large:
        return f"File '{too_large.filename}' is too large (> {max_bytes // (1024 * 1024)} MB)", 400
    return None, None


def _file_size(f: FileStorage) -> int:
    """Возвращает размер файла в байтах.
    - Если `content_length` указан — пользуемся им.
    - Иначе аккуратно измеряем длину stream'а (с сохранением позиции курсора)."""
    if getattr(f, "content_length", None):
        return int(f.content_length)

    pos = f.stream.tell()
    f.stream.seek(0, os.SEEK_END)
    size = f.stream.tell()
    f.stream.seek(pos)
    return size


def _check_mp3_extension_and_size(f: FileStorage, max_bytes: int) -> str | None:
    """Проверка файлов"""
    if not f.filename.lower().endswith(".mp3"):
        return "File must have .mp3 extension"

    size = _file_size(f)
    if size == 0:
        return f"File {f.filename} is empty"
    if size > max_bytes:
        return f"File {f.filename} is too large (> {max_bytes // (1024 * 1024)} MB)"
    return None


def validate_merge_request(
    req: Request,
    max_files: int,
    max_per_file_mb: int,
    ffmpeg_available: bool,
    check_files_are_mp3_fn,
) -> ValidationResult:
    """Возвращает ValidationResult с error_response=None, если ошибок нет."""

    files: list[Any] | None = None
    count: int | None = None
    error: str | None = None
    code: int | None = None

    # 1) Content-Type
    if error is None:
        error, code = _check_content_type(req)

    # 2) files + count
    if error is None:
        raw = req.files.getlist("files")
        files = _filter_empty_files(raw)
        if not files:
            error, code = "No files provided", 400
        else:
            count = req.form.get("count", type=int)
            error, code = _check_files_and_count(files, count, max_files)

    # 3) FFmpeg
    if error is None and not ffmpeg_available:
        error, code = "FFmpeg is not available in runtime", 500

    # 4) mp3-валидность
    if error is None:
        mp3_err = check_files_are_mp3_fn(files)  # type: ignore[arg-type]
        if mp3_err:
            error, code = mp3_err[0]["error"], mp3_err[1]

    # 5) размеры и расширение
    if error is None:
        max_bytes = max_per_file_mb * 1024 * 1024
        for f in files:  # type: ignore[arg-type]
            err = _check_mp3_extension_and_size(f, max_bytes)
            if err:
                error, code = err, 400
                break
        if error is None:
            error, code = _check_sizes(files, max_bytes)  # type: ignore[arg-type]

    if error is not None:
        return ValidationResult(None, None, jsonify({"error": error}), code)  # type: ignore[arg-type]

    return ValidationResult(files, count, None, None)  # type: ignore[arg-type]
