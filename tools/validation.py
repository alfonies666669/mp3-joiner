from typing import Any, NamedTuple

from flask import Request, Response, jsonify


class ValidationResult(NamedTuple):
    files: list[Any] | None
    count: int | None
    error_response: Response | None
    status_code: int | None


def _check_content_type(req: Request) -> tuple[str | None, int]:
    if req.mimetype != "multipart/form-data":
        return "Content-Type must be multipart/form-data", 415
    return None, 400


def _check_files_and_count(files: list[Any], count: int | None, max_files: int) -> tuple[str | None, int]:
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
    too_large = next(
        (f for f in files if (getattr(f, "content_length", None) or 0) > max_bytes),
        None,
    )
    if too_large:
        return f"File '{too_large.filename}' is too large (> {max_bytes // (1024 * 1024)} MB)", 400
    return None, 400


def validate_merge_request(
    req: Request,
    max_files: int,
    max_per_file_mb: int,
    ffmpeg_available: bool,
    check_files_are_mp3_fn,
) -> ValidationResult:
    # 1. Content-Type
    error_msg, error_code = _check_content_type(req)
    if error_msg:
        return ValidationResult(None, None, jsonify({"error": error_msg}), error_code)

    # 2. Files + count
    files = req.files.getlist("files")
    count = req.form.get("count", type=int)

    error_msg, error_code = _check_files_and_count(files, count, max_files)
    if error_msg:
        return ValidationResult(None, None, jsonify({"error": error_msg}), error_code)

    # 3. FFmpeg
    if not ffmpeg_available:
        return ValidationResult(None, None, jsonify({"error": "FFmpeg is not available in runtime"}), 500)

    # 4. Size check
    max_bytes = max_per_file_mb * 1024 * 1024
    error_msg, error_code = _check_sizes(files, max_bytes)
    if error_msg:
        return ValidationResult(None, None, jsonify({"error": error_msg}), error_code)

    # 5. MP3 check
    mp3_error = check_files_are_mp3_fn(files)
    if mp3_error:
        return ValidationResult(None, None, jsonify(mp3_error[0]), mp3_error[1])

    # OK
    return ValidationResult(files, count, None, None)
