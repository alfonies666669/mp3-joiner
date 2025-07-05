import io
import os
import zipfile

import pytest
from mutagen.mp3 import HeaderNotFoundError
from werkzeug.datastructures import FileStorage

from tools import utils

# ---------- check_files_are_mp3 ----------


def _fs(name: str, payload: bytes = b"ID3\x00\x00\x00aaaa"):
    return FileStorage(stream=io.BytesIO(payload), filename=name, content_type="audio/mpeg")


def test_check_files_are_mp3_ok(monkeypatch):
    monkeypatch.setattr(utils, "MP3", lambda stream: object())
    files = [_fs("a.mp3"), _fs("b.mp3")]
    assert utils.check_files_are_mp3(files) is None
    for f in files:
        assert f.stream.tell() == 0


def test_check_files_are_mp3_header_error(monkeypatch):
    def boom(_stream):
        raise HeaderNotFoundError("bad header")

    monkeypatch.setattr(utils, "MP3", boom)
    files = [_fs("broken.mp3")]
    err = utils.check_files_are_mp3(files)
    assert isinstance(err, tuple) and err[1] == 400
    assert "broken.mp3" in err[0]["error"]


def test_check_files_are_mp3_generic_error(monkeypatch):
    def boom(_stream):
        raise RuntimeError("weird")

    monkeypatch.setattr(utils, "MP3", boom)
    files = [_fs("bad.mp3")]
    err = utils.check_files_are_mp3(files)
    assert err[1] == 400
    assert "bad.mp3" in err[0]["error"]


# ---------- saving_files ----------


def test_saving_files_writes_and_uses_normalized_name(tmp_path, monkeypatch):
    # нормализация имени
    monkeypatch.setattr(utils.Merge, "normalize_filename", lambda n: "clean.mp3")
    f = _fs("../dirty..name .mp3", payload=b"X")
    paths = utils.saving_files(str(tmp_path), [f])
    assert len(paths) == 1
    assert os.path.basename(paths[0]) == "clean.mp3"
    with open(paths[0], "rb") as fh:
        assert fh.read() == b"X"


def test_saving_files_raises_on_failure(tmp_path, monkeypatch):
    class BadFS(FileStorage):
        def save(self, dst, *a, **k):
            raise OSError("disk full")

    f = BadFS(stream=io.BytesIO(b"x"), filename="a.mp3")
    with pytest.raises(RuntimeError) as exc:
        utils.saving_files(str(tmp_path), [f])
    assert "Ошибка при сохранении a.mp3" in str(exc.value)


# ---------- smart_merge_mp3_files ----------


def test_smart_merge_fast_path(monkeypatch, tmp_path):
    files = [str(tmp_path / "1.mp3"), str(tmp_path / "2.mp3")]
    for p in files:
        open(p, "wb").close()

    monkeypatch.setattr(utils.Merge, "all_params_equal", lambda _: True)
    called = {"merge_in_groups": False}

    def fake_merge(file_list, group_size, output_folder):
        called["merge_in_groups"] = True
        os.makedirs(output_folder, exist_ok=True)  # ← ВАЖНО
        out = os.path.join(output_folder, "merged_1.mp3")
        with open(out, "wb"):
            pass
        return [out]

    monkeypatch.setattr(utils.Merge, "merge_files_in_groups", fake_merge)
    out = utils.smart_merge_mp3_files(files, 2, str(tmp_path / "out"))
    assert called["merge_in_groups"] is True
    assert len(out) == 1 and out[0].endswith("merged_1.mp3")


def test_smart_merge_normalize_then_ffmpeg(monkeypatch, tmp_path):
    files = [str(tmp_path / "a.mp3"), str(tmp_path / "b.mp3")]
    for p in files:
        open(p, "wb").close()

    monkeypatch.setattr(utils.Merge, "all_params_equal", lambda _: False)
    monkeypatch.setattr(
        utils.Merge, "normalize_mp3_file_parallel", lambda file_paths, merged_folder: ["n1.mp3", "n2.mp3"]
    )

    called = {"concat": False}

    def fake_concat(file_list, group_size, output_folder):
        called["concat"] = True
        os.makedirs(output_folder, exist_ok=True)
        out = os.path.join(output_folder, "merged_1.mp3")
        with open(out, "wb"):
            pass
        return [out]

    monkeypatch.setattr(utils.Merge, "merge_mp3_groups_ffmpeg", fake_concat)

    out = utils.smart_merge_mp3_files(files, 2, str(tmp_path / "out"))
    assert called["concat"] is True
    assert len(out) == 1 and out[0].endswith("merged_1.mp3")


# ---------- create_zip ----------


def test_create_zip_ok(tmp_path):
    merged_dir = tmp_path / "m"
    merged_dir.mkdir()
    f1 = merged_dir / "x.mp3"
    f1.write_bytes(b"xxx")

    zip_path = utils.create_zip(str(merged_dir), [str(f1)])
    assert os.path.exists(zip_path)
    with zipfile.ZipFile(zip_path) as z:
        assert sorted(z.namelist()) == ["x.mp3"]


def test_create_zip_warns_on_missing_but_continues(tmp_path, caplog):
    merged_dir = tmp_path / "m"
    merged_dir.mkdir()
    f1 = merged_dir / "x.mp3"
    f1.write_bytes(b"xxx")

    missing = merged_dir / "absent.mp3"
    zip_path = utils.create_zip(str(merged_dir), [str(f1), str(missing)])
    assert os.path.exists(zip_path)
    with zipfile.ZipFile(zip_path) as z:
        assert z.namelist() == ["x.mp3"]


def test_create_zip_raises_on_empty_list(tmp_path):
    merged_dir = tmp_path / "m"
    merged_dir.mkdir()
    with pytest.raises(RuntimeError):
        utils.create_zip(str(merged_dir), [])
