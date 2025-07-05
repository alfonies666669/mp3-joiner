import types

from tools import system


def test_ffmpeg_ok_success(monkeypatch):
    def fake_run(*args, **kwargs):
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(system.subprocess, "run", fake_run)

    assert system.ffmpeg_ok() is True


def test_ffmpeg_ok_nonzero(monkeypatch):
    def fake_run(*args, **kwargs):
        return types.SimpleNamespace(returncode=1)

    monkeypatch.setattr(system.subprocess, "run", fake_run)

    assert system.ffmpeg_ok() is False


def test_ffmpeg_ok_exception(monkeypatch):
    def fake_run(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(system.subprocess, "run", fake_run)

    assert system.ffmpeg_ok() is False
