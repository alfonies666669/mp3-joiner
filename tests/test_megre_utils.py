"""Тесты для модуля tools.merge_utils (класс Merge).

Покрываются:
- нормализация имён файлов;
- проверка all_params_equal;
- байтовый merge в группах;
- нормализация MP3 через ffmpeg (моки);
- объединение MP3 через ffmpeg concat (моки).
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from tools.merge_utils import Merge

# ---------- normalize_filename ----------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("  Абв.mp3  ", "Абв.mp3"),
        ("a  b   c.mp3", "a_b_c.mp3"),
        ("../weird/..//name..mp3", "weird..name..mp3"),
        ("name___.mp3", "name.mp3"),
        ("na?me*|<>.mp3", "name.mp3"),
        ("     .hidden..mp3..   ", "hidden..mp3"),
    ],
)
def test_normalize_filename(raw: str, expected: str) -> None:
    """normalize_filename корректно чистит странные имена файлов."""
    assert Merge.normalize_filename(raw) == expected


# ---------- all_params_equal ----------


def test_all_params_equal_true(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Все файлы имеют одинаковые параметры MP3 → возвращает True."""
    files = [str(tmp_path / f"f{i}.mp3") for i in range(3)]
    for p in files:
        with open(p, "wb"):
            pass

    monkeypatch.setattr(Merge, "_get_mp3_params", lambda _: (192000, 44100, 2))
    assert Merge.all_params_equal(files) is True


def test_all_params_equal_false(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Файлы с разными параметрами MP3 → возвращает False."""
    files = [str(tmp_path / f"f{i}.mp3") for i in range(3)]
    for p in files:
        with open(p, "wb"):
            pass

    params = [(192000, 44100, 2), (128000, 44100, 2), (192000, 48000, 2)]

    def fake_get(path: str):
        i = int(os.path.basename(path)[1])  # f0/f1/f2
        return params[i]

    monkeypatch.setattr(Merge, "_get_mp3_params", fake_get)
    assert Merge.all_params_equal(files) is False


# ---------- merge_files_in_groups ----------


def test_merge_files_in_groups_basic(tmp_path) -> None:
    """Байтовый merge по группам: 5 входов → 3 выхода, проверяем содержимое."""
    inputs = []
    for i in range(5):
        p = tmp_path / f"in{i}.mp3"
        with open(p, "wb") as f:
            f.write(f"FILE{i}-".encode())
        inputs.append(str(p))

    out_dir = tmp_path / "out"
    merged = Merge.merge_files_in_groups(inputs, group_size=2, output_folder=str(out_dir))
    assert len(merged) == 3
    assert [os.path.basename(m) for m in merged] == [
        "merged_1.mp3",
        "merged_2.mp3",
        "merged_3.mp3",
    ]

    with open(merged[0], "rb") as f:
        assert f.read() == b"FILE0-FILE1-"
    with open(merged[1], "rb") as f:
        assert f.read() == b"FILE2-FILE3-"
    with open(merged[2], "rb") as f:
        assert f.read() == b"FILE4-"


def test_merge_files_in_groups_skips_missing(tmp_path) -> None:
    """Отсутствующий файл пропускается, но merge продолжается."""
    p1 = tmp_path / "a.mp3"
    p1.write_bytes(b"A-")
    missing = tmp_path / "missing.mp3"
    out_dir = tmp_path / "out"
    merged = Merge.merge_files_in_groups([str(p1), str(missing)], 2, str(out_dir))
    assert len(merged) == 1
    with open(merged[0], "rb") as f:
        assert f.read() == b"A-"


# ---------- normalize_mp3_file_parallel ----------


def test_normalize_mp3_file_parallel_success(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """ffmpeg возвращает 0 → все файлы нормализуются успешно."""
    inp = []
    for i in range(3):
        p = tmp_path / f"in{i}.mp3"
        p.write_bytes(b"ID3....")
        inp.append(str(p))

    monkeypatch.setattr("subprocess.run", lambda *_, **__: SimpleNamespace(returncode=0, stderr=b""))

    out_dir = tmp_path / "norm"
    res = Merge.normalize_mp3_file_parallel(inp, str(out_dir))
    assert len(res) == 3
    for i, p in enumerate(res):
        assert p.endswith(f"normalized_in{i}.mp3")


def test_normalize_mp3_file_parallel_partial_fail(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Если ffmpeg вернул !=0 для одного файла, он → None, остальные нормализуются."""
    files = []
    for name in ["a.mp3", "b.mp3"]:
        p = tmp_path / name
        p.write_bytes(b"x")
        files.append(str(p))

    calls = {"n": 0}

    def fake_run(*_, **__):
        calls["n"] += 1
        return SimpleNamespace(returncode=0 if calls["n"] == 1 else 1, stderr=b"boom")

    monkeypatch.setattr("subprocess.run", fake_run)
    res = Merge.normalize_mp3_file_parallel(files, str(tmp_path / "out"))
    assert res[0] and res[0].endswith("normalized_a.mp3")
    assert res[1] is None


# ---------- merge_mp3_groups_ffmpeg ----------


def test_merge_mp3_groups_ffmpeg_success(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """ffmpeg concat проходит успешно: возвращаем пути merged_*.mp3."""
    files = [str(tmp_path / f"n{i}.mp3") for i in range(4)]
    for p in files:
        with open(p, "wb"):
            pass

    monkeypatch.setattr("subprocess.run", lambda *_, **__: SimpleNamespace(returncode=0, stderr=b""))

    out_dir = tmp_path / "out"
    res = Merge.merge_mp3_groups_ffmpeg(files, 3, str(out_dir))
    assert [os.path.basename(p) for p in res] == ["merged_1.mp3", "merged_2.mp3"]


def test_merge_mp3_groups_ffmpeg_failure(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Если ffmpeg падает на первой группе — она пропускается, сохраняется только вторая."""
    files = [str(tmp_path / f"n{i}.mp3") for i in range(3)]
    for p in files:
        with open(p, "wb"):
            pass

    calls = {"n": 0}

    def fake_run(*_, **__):
        calls["n"] += 1
        return SimpleNamespace(returncode=1 if calls["n"] == 1 else 0, stderr=b"bad")

    monkeypatch.setattr("subprocess.run", fake_run)
    res = Merge.merge_mp3_groups_ffmpeg(files, 2, str(tmp_path / "out"))
    assert [os.path.basename(p) for p in res] == ["merged_2.mp3"]
