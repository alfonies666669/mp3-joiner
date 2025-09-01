"""Валидация входного запроса для эндпоинта /merge.

Модуль разбивает проверки на мелкие функции:
- _check_content_type: корректность Content-Type;
- _check_files_and_count: наличие файлов и валидность параметра count;
- _check_sizes: ограничение на размер каждого файла;
- validate_merge_request: координирует все проверки и формирует единый результат.
"""

from typing import Any, NamedTuple
from collections.abc import Callable

from flask import Request, Response, jsonify

from logger import app_logger


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


def _filter_empty_files(raw: list[Any]) -> list[Any]:
    """Убирает части без содержимого или имени файла."""
    result: list[Any] = []
    for part in raw:
        if not getattr(part, "filename", "").strip():
            app_logger.debug("skip part: empty filename")
            continue
        size = getattr(part, "content_length", None) or 0
        if size == 0:
            app_logger.debug("skip part: zero length %s", part.filename)
            continue
        result.append(part)
    return result


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


def _check_sizes(files: list[Any], max_bytes: int) -> tuple[str | None, int]:
    """Проверяет, что каждый файл не превышает заданный размер.

    :param files: Список объектов FileStorage.
    :param max_bytes: Максимально допустимый размер одного файла в байтах.
    :return: (сообщение_об_ошибке | None, http_код). Если всё ок — (None, 400).
    """
    too_large = next(
        (f for f in files if (getattr(f, "content_length", None) or 0) > max_bytes),
        None,
    )
    if too_large:
        return f"File '{too_large.filename}' is too large (> {max_bytes // (1024 * 1024)} MB)", 400
    return None, 400


def _check_mp3_extension_and_size(file, max_bytes):
    """Проверка файлов"""
    if not file.filename.lower().endswith(".mp3"):
        return f"File {file.filename} must have .mp3 extension"
    if (getattr(file, "content_length", 0) or 0) == 0:
        return f"File {file.filename} is empty"
    if (getattr(file, "content_length", 0) or 0) > max_bytes:
        return f"File {file.filename} is too large"
    return None


def validate_merge_request(
    req: Request,
    max_files: int,
    max_per_file_mb: int,
    ffmpeg_available: bool,
    check_files_are_mp3_fn: Callable[None | tuple],
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

    # 4) размеры и расширение
    if error is None:
        max_bytes = max_per_file_mb * 1024 * 1024
        for f in files:  # type: ignore[arg-type]
            err = _check_mp3_extension_and_size(f, max_bytes)
            if err:
                error, code = err, 400
                break
        if error is None:
            error, code = _check_sizes(files, max_bytes)  # type: ignore[arg-type]

    # 5) mp3-валидность
    if error is None:
        mp3_err = check_files_are_mp3_fn(files)  # type: ignore[arg-type]
        if mp3_err:
            error, code = mp3_err[0]["error"], mp3_err[1]

    if error is not None:
        return ValidationResult(None, None, jsonify({"error": error}), code)  # type: ignore[arg-type]

    return ValidationResult(files, count, None, None)  # type: ignore[arg-type]
