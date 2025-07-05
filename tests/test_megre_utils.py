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
def test_normalize_filename(raw, expected):
    assert Merge.normalize_filename(raw) == expected


# ---------- all_params_equal ----------


def test_all_params_equal_true(monkeypatch, tmp_path):
    files = [str(tmp_path / f"f{i}.mp3") for i in range(3)]
    for p in files:
        open(p, "wb").close()

    monkeypatch.setattr(Merge, "_get_mp3_params", lambda _: (192000, 44100, 2))
    assert Merge.all_params_equal(files) is True


def test_all_params_equal_false(monkeypatch, tmp_path):
    files = [str(tmp_path / f"f{i}.mp3") for i in range(3)]
    for p in files:
        open(p, "wb").close()

    params = [(192000, 44100, 2), (128000, 44100, 2), (192000, 48000, 2)]

    def fake_get(path):
        i = int(os.path.basename(path)[1])  # f0/f1/f2
        return params[i]

    monkeypatch.setattr(Merge, "_get_mp3_params", fake_get)
    assert Merge.all_params_equal(files) is False


# ---------- merge_files_in_groups (байтовый конкат) ----------


def test_merge_files_in_groups_basic(tmp_path):
    # создаём 5 «mp3» (на самом деле просто байты) и проверяем групповой merge
    inputs = []
    for i in range(5):
        p = tmp_path / f"in{i}.mp3"
        with open(p, "wb") as f:
            f.write(f"FILE{i}-".encode())
        inputs.append(str(p))

    out_dir = tmp_path / "out"
    merged = Merge.merge_files_in_groups(inputs, group_size=2, output_folder=str(out_dir))
    # ожидаем 3 файла: [in0,in1], [in2,in3], [in4]
    assert len(merged) == 3
    assert os.path.basename(merged[0]) == "merged_1.mp3"
    assert os.path.basename(merged[1]) == "merged_2.mp3"
    assert os.path.basename(merged[2]) == "merged_3.mp3"

    # проверяем содержимое: это простой конкат
    with open(merged[0], "rb") as f:
        assert f.read() == b"FILE0-FILE1-"
    with open(merged[1], "rb") as f:
        assert f.read() == b"FILE2-FILE3-"
    with open(merged[2], "rb") as f:
        assert f.read() == b"FILE4-"


def test_merge_files_in_groups_skips_missing(tmp_path):
    # один из входов отсутствует — предупреждение в логах, но файл всё равно создаётся из оставшихся
    p1 = tmp_path / "a.mp3"
    p1.write_bytes(b"A-")
    missing = tmp_path / "missing.mp3"
    out_dir = tmp_path / "out"
    merged = Merge.merge_files_in_groups([str(p1), str(missing)], group_size=2, output_folder=str(out_dir))
    assert len(merged) == 1
    with open(merged[0], "rb") as f:
        assert f.read() == b"A-"


# ---------- normalize_mp3_file_parallel (мокаем ffmpeg) ----------


def test_normalize_mp3_file_parallel_success(monkeypatch, tmp_path):
    inp = []
    for i in range(3):
        p = tmp_path / f"in{i}.mp3"
        p.write_bytes(b"ID3....")
        inp.append(str(p))

    # ffmpeg OK
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=b"", stderr=b""),
    )

    out_dir = tmp_path / "norm"
    res = Merge.normalize_mp3_file_parallel(inp, str(out_dir), sample_rate=44100, bit_rate=192, channels=2)
    # список из строк путей; порядок сохранён
    assert len(res) == 3
    for i, p in enumerate(res):
        assert p.endswith(f"normalized_in{i}.mp3")


def test_normalize_mp3_file_parallel_partial_fail(monkeypatch, tmp_path):
    p0 = tmp_path / "a.mp3"
    p0.write_bytes(b"x")
    p1 = tmp_path / "b.mp3"
    p1.write_bytes(b"x")
    files = [str(p0), str(p1)]

    # первый успех, второй провал
    calls = {"n": 0}

    def fake_run(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        return SimpleNamespace(returncode=1, stdout=b"", stderr=b"boom")

    monkeypatch.setattr("subprocess.run", fake_run)
    res = Merge.normalize_mp3_file_parallel(files, str(tmp_path / "out"))
    assert len(res) == 2
    # второй элемент должен быть None
    assert res[0] and res[0].endswith("normalized_a.mp3")
    assert res[1] is None


# ---------- merge_mp3_groups_ffmpeg (мокаем ffmpeg) ----------


def test_merge_mp3_groups_ffmpeg_success(monkeypatch, tmp_path):
    # входные "нормализованные" пути
    files = [str(tmp_path / f"n{i}.mp3") for i in range(4)]
    for p in files:
        open(p, "wb").close()

    # имитируем успешный ffmpeg
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=b"", stderr=b""),
    )

    out_dir = tmp_path / "out"
    res = Merge.merge_mp3_groups_ffmpeg(files, group_size=3, output_folder=str(out_dir))
    # ожидаем 2 файла: [0,1,2] и [3]
    assert [os.path.basename(p) for p in res] == ["merged_1.mp3", "merged_2.mp3"]


def test_merge_mp3_groups_ffmpeg_failure(monkeypatch, tmp_path):
    files = [str(tmp_path / f"n{i}.mp3") for i in range(3)]
    for p in files:
        open(p, "wb").close()

    # первый запуск — ошибка, второй — успех
    calls = {"n": 0}

    def fake_run(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return SimpleNamespace(returncode=1, stdout=b"", stderr=b"bad")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr("subprocess.run", fake_run)
    out_dir = tmp_path / "out"
    res = Merge.merge_mp3_groups_ffmpeg(files, group_size=2, output_folder=str(out_dir))
    # первая группа (2 файла) провалилась → только вторая (1 файл) прошла
    assert [os.path.basename(p) for p in res] == ["merged_2.mp3"]
