"""System utilities: FFmpeg availability check."""

import subprocess

from logger.logger import app_logger


def ffmpeg_ok() -> bool:
    """
    Проверяет, доступен ли ffmpeg в окружении.
    :return: True, если утилита установлена и возвращает код 0.
    """
    try:
        res = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=False,
        )
        return res.returncode == 0
    except Exception as e:
        app_logger.error("FFmpeg check failed: %s", e)
        return False
