import os
import json
import logging
import importlib
import contextlib
from pathlib import Path

import pytest


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    """Чистим переменные окружения и даём свежие пути под логи."""
    monkeypatch.delenv("LOG_DIR", raising=False)
    monkeypatch.delenv("USER_LOG_PATH", raising=False)
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "app_logs"))
    return tmp_path


def _reload_logger_module():
    import logger.logger as logger_module

    importlib.reload(logger_module)
    return logger_module


def test_app_logger_rotating_file_handler_created(clean_env):
    logger_module = _reload_logger_module()

    # Проверка: директория создана
    log_dir = Path(os.environ["LOG_DIR"])
    assert log_dir.exists() and log_dir.is_dir()

    # Хэндлер есть и пишет в файл
    assert isinstance(logger_module.app_logger, logging.Logger)
    # Извлечём единственный хэндлер
    handlers = logger_module.app_logger.handlers
    assert handlers, "app_logger должен иметь хотя бы один хэндлер"
    rh = handlers[0]
    # Имя файла корректно
    # RotatingFileHandler имеет baseFilename
    assert "app.log" in getattr(rh, "baseFilename", "")


def test_user_logger_disabled_when_env_missing(clean_env, monkeypatch):
    monkeypatch.delenv("USER_LOG_PATH", raising=False)
    logger_module = _reload_logger_module()

    assert logger_module.user_logger is None


def test_user_logger_with_directory_path(clean_env, monkeypatch):
    # USER_LOG_PATH указывает на директорию — должен создаться/использоваться файл user_actions.json
    user_dir = clean_env / "user_logs"
    user_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_LOG_PATH", str(user_dir))

    logger_module = _reload_logger_module()
    ul = logger_module.user_logger
    assert ul is not None

    # Найдём хэндлер и путь файла
    handlers = ul.handlers
    assert handlers, "user_logger должен иметь хэндлер"
    fh = handlers[0]
    log_file = Path(getattr(fh, "baseFilename", ""))
    assert log_file.name == "user_actions.json"

    # Запишем запись с extra
    ul.info("hello", extra={"extra": {"event": "test_evt", "k": 1}})
    # Сбросим буферы
    for h in handlers:
        h.flush()

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8").strip()
    assert content, "лог пустой"
    # Проверим JSON-формат и наличие полей
    rec = json.loads(content)
    assert rec["message"] == "hello"
    assert rec["event"] == "test_evt"
    assert rec["k"] == 1
    assert rec["logger"] == "user_actions"
    assert "timestamp" in rec
    assert "level" in rec


def test_user_logger_with_file_path(clean_env, monkeypatch):
    user_file = clean_env / "custom.jsonl"
    monkeypatch.setenv("USER_LOG_PATH", str(user_file))

    logger_module = _reload_logger_module()
    ul = logger_module.user_logger
    assert ul is not None

    ul.warning("warn", extra={"extra": {"ip": "1.2.3.4"}})

    # найдём файловый хэндлер и возьмём реальный путь
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


def test_user_logger_idempotent_handlers(clean_env, monkeypatch):
    """Повторная загрузка модуля не должна дублировать хэндлеры."""
    user_file = clean_env / "dup.jsonl"
    monkeypatch.setenv("USER_LOG_PATH", str(user_file))

    m1 = _reload_logger_module()
    h_count_1 = len(m1.user_logger.handlers)

    m2 = _reload_logger_module()
    h_count_2 = len(m2.user_logger.handlers)

    assert h_count_1 == h_count_2 == 1, "не должно плодиться много хэндлеров"
