"""Тесты для tools.system.ffmpeg_ok.

Проверяем:
- успешный запуск ffmpeg (returncode == 0);
- неуспешный запуск (returncode != 0);
- обработку исключения при вызове subprocess.run.
"""

from types import SimpleNamespace

from tools import system


def test_ffmpeg_ok_success(monkeypatch):
    """Если subprocess.run возвращает returncode=0 — ffmpeg_ok() -> True."""

    def fake_run(*_, **__):
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(system.subprocess, "run", fake_run)
    assert system.ffmpeg_ok() is True


def test_ffmpeg_ok_nonzero(monkeypatch):
    """Если subprocess.run возвращает returncode!=0 — ffmpeg_ok() -> False."""

    def fake_run(*_, **__):
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(system.subprocess, "run", fake_run)
    assert system.ffmpeg_ok() is False


def test_ffmpeg_ok_exception(monkeypatch):
    """Если subprocess.run выбрасывает исключение — ffmpeg_ok() -> False."""

    def fake_run(*_, **__):
        raise RuntimeError("boom")

    monkeypatch.setattr(system.subprocess, "run", fake_run)
    assert system.ffmpeg_ok() is False
