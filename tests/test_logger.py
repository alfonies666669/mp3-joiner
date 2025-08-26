"""Тесты модуля логирования: app_logger и user_logger.

Проверяем:
- создание/конфигурацию файлового хэндлера для app_logger;
- инициализацию/отключение user_logger в зависимости от переменных окружения;
- корректность JSON-формата и записи extra-полей;
- идемпотентность и отсутствие дублирования хэндлеров при повторной загрузке модуля.
"""

# pylint: disable=redefined-outer-name, protected-access, unused-argument
from __future__ import annotations

import os
import json
import logging
import importlib
import contextlib
from pathlib import Path

import pytest


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Чистит переменные окружения, задаёт свежую директорию логов и возвращает tmp_path."""
    monkeypatch.delenv("LOG_DIR", raising=False)
    monkeypatch.delenv("USER_LOG_PATH", raising=False)
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "app_logs"))
    return tmp_path


def _reload_logger_module():
    """Перезагружает модуль логирования с учётом актуальных переменных окружения."""
    # pylint: disable=import-outside-toplevel
    import logger.logger as logger_module

    importlib.reload(logger_module)
    return logger_module


def test_app_logger_rotating_file_handler_created(clean_env: Path) -> None:
    """app_logger создаёт RotatingFileHandler и пишет в LOG_DIR/app.log."""
    logger_module = _reload_logger_module()

    log_dir = Path(os.environ["LOG_DIR"])
    assert log_dir.exists() and log_dir.is_dir()

    assert isinstance(logger_module.app_logger, logging.Logger)
    handlers = logger_module.app_logger.handlers
    assert handlers, "app_logger должен иметь хотя бы один хэндлер"
    rh = handlers[0]
    assert "app.log" in getattr(rh, "baseFilename", "")


def test_user_logger_disabled_when_env_missing(_clean_env: Path) -> None:
    """При отсутствии USER_LOG_PATH — user_logger == None."""
    logger_module = _reload_logger_module()
    assert logger_module.user_logger is None


def test_user_logger_with_directory_path(clean_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """USER_LOG_PATH=директория → создаётся файл user_actions.json, JSON-лог корректный."""
    user_dir = clean_env / "user_logs"
    user_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_LOG_PATH", str(user_dir))

    logger_module = _reload_logger_module()
    ul = logger_module.user_logger
    assert ul is not None

    handlers = ul.handlers
    assert handlers, "user_logger должен иметь хэндлер"
    fh = handlers[0]
    log_file = Path(getattr(fh, "baseFilename", ""))
    assert log_file.name == "user_actions.json"

    ul.info("hello", extra={"extra": {"event": "test_evt", "k": 1}})
    for h in handlers:
        h.flush()

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8").strip()
    assert content, "лог пустой"

    rec = json.loads(content)
    assert rec["message"] == "hello"
    assert rec["event"] == "test_evt"
    assert rec["k"] == 1
    assert rec["logger"] == "user_actions"
    assert "timestamp" in rec
    assert "level" in rec


def test_user_logger_with_file_path(clean_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """USER_LOG_PATH=файл → пишем JSON-строки в указанный файл; проверяем содержимое."""
    user_file = clean_env / "custom.jsonl"
    monkeypatch.setenv("USER_LOG_PATH", str(user_file))

    logger_module = _reload_logger_module()
    ul = logger_module.user_logger
    assert ul is not None

    ul.warning("warn", extra={"extra": {"ip": "1.2.3.4"}})

    fh = next(h for h in ul.handlers if hasattr(h, "baseFilename"))
    real_path = Path(fh.baseFilename)

    fh.flush()
    with contextlib.suppress(Exception):
        os.fsync(fh.stream.fileno())

    assert real_path.exists(), f"лог не создан: {real_path}"

    lines = real_path.read_text(encoding="utf-8").splitlines()
    assert lines, "ожидаем хотя бы одну строку"

    rec = json.loads(lines[-1])
    assert rec["message"] == "warn"
    assert rec["ip"] == "1.2.3.4"
    assert rec["level"] == "WARNING"


def test_user_logger_idempotent_handlers(clean_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Повторная загрузка модуля не должна дублировать файловые хэндлеры."""
    user_file = clean_env / "dup.jsonl"
    monkeypatch.setenv("USER_LOG_PATH", str(user_file))

    m1 = _reload_logger_module()
    h_count_1 = len(m1.user_logger.handlers)

    m2 = _reload_logger_module()
    h_count_2 = len(m2.user_logger.handlers)

    assert h_count_1 == h_count_2 == 1, "не должно плодиться много хэндлеров"
