from flask import jsonify

from logger.logger import app_logger


def bad_request(msg: str, code: int = 400):
    app_logger.warning("Bad request: %s", msg)
    return jsonify({"error": msg}), code


def server_error(msg: str = "Internal server error"):
    app_logger.error("Server error: %s", msg)
    return jsonify({"error": msg}), 500


def handle_413(max_content_length: int):
    def _handler(_e):
        app_logger.error("Request entity too large")
        return jsonify({"error": f"The total upload is too large (> {max_content_length / (1024 * 1024)} MB)."}), 413

    return _handler
