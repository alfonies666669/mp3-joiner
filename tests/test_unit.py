"""
Тесты для модулей tools.utils и tools.merge_utils.
"""

import os
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from werkzeug.datastructures import FileStorage

from tools.merge_utils import Merge
from tools.utils import create_zip, saving_files, merge_mp3_files_ffmpeg


@pytest.mark.parametrize(
    "input_name, expected_name",
    [
        ("привет мир.mp3", "привет_мир.mp3"),
        ("тест/файл.mp3", "тестфайл.mp3"),
        ("документ.pdf", "документ.pdf"),
        ("file/<test>.mp3", "filetest.mp3"),
        ('bad:"name"|*?.mp3', "badname.mp3"),
        ("remove/\\<>:?*\"'|@#$%^&+=`test.mp3", "removetest.mp3"),
        ("   spaces   .mp3", "spaces.mp3"),
        ("  leading and trailing  ", "leading_and_trailing"),
        ("multiple   spaces", "multiple_spaces"),
        ("smile 😃.mp3", "smile.mp3"),
        ("music 🎵.mp3", "music.mp3"),
        ("🔥 hot track 🔥.mp3", "hot_track.mp3"),
        ("", ""),
        ("....", ""),
        ("._._.", ""),
        ("-_-_-", "-_-_-"),
        ("a" * 255, "a" * 255),
    ],
)
def test_normalize_filename(input_name, expected_name):
    """
    Проверяет корректную нормализацию имён файлов.

    :param input_name: Входное имя файла
    :param expected_name: ожидаемое нормализованное имя
    """
    assert Merge.normalize_filename(input_name) == expected_name


def test_merge_strings():
    """
    Проверяет разбиение списка на подгруппы по заданному количеству элементов.
    """
    result = Merge.merge_strings(["a", "b", "c", "d"], count=2)
    assert result == ["a b", "c d"]

    result = Merge.merge_strings(["a", "b", "c", "d"], count=3)
    assert result == ["a b c", "d"]


def test_create_ffmpeg_input_file(tmpdir):
    """
    Проверяет создание временного файла с путями файлов для FFmpeg.

    :param tmpdir: Временная директория
    """
    file_paths = [str(Path(tmpdir) / f"file{i}.mp3") for i in range(3)]
    input_file = str(Path(tmpdir) / "input.txt")

    result = Merge.create_ffmpeg_input_file(file_paths, input_file)

    assert result == input_file
    with open(input_file, encoding="utf-8") as f:
        lines = f.readlines()
    assert lines == [f"file '{path}'\n" for path in file_paths]


def test_saving_files(tmpdir):
    """
    Проверяет сохранение загруженных файлов в указанной директории.

    :param tmpdir: Временная директория
    """
    upload_folder = str(tmpdir.mkdir("uploads"))
    files = [
        FileStorage(BytesIO(b"fake audio data"), filename="   Test_файл!.mp3"),
        FileStorage(BytesIO(b"another fake data"), filename="track 2.mp3"),
    ]
    saved_paths = saving_files(upload_folder, files)
    assert len(saved_paths) == 2
    assert os.path.basename(saved_paths[0]) == "Test_файл.mp3"
    assert os.path.basename(saved_paths[1]) == "track_2.mp3"
    for path in saved_paths:
        assert os.path.exists(path)


def test_create_zip(tmpdir):
    """
    Проверяет создание ZIP-архива из объединённых файлов.

    :param tmpdir: Временная директория
    """
    merged_folder = tmpdir.mkdir("merged")
    file1 = merged_folder.join("file1.mp3")
    file2 = merged_folder.join("file2.mp3")
    file1.write("data1")
    file2.write("data2")

    archive_path = create_zip(str(merged_folder), [str(file1), str(file2)])

    assert os.path.exists(archive_path)
    with zipfile.ZipFile(archive_path, "r") as zipf:
        assert "file1.mp3" in zipf.namelist()
        assert "file2.mp3" in zipf.namelist()


@patch("tools.utils.subprocess.run")
@patch("tools.merge_utils.Merge.normalize_mp3_file_parallel")
@patch("tools.merge_utils.Merge.create_ffmpeg_input_file")
def test_merge_mp3_files_ffmpeg(mock_input, mock_norm, mock_run, tmpdir):
    """
    Проверяет функцию объединения MP3 через FFmpeg.

    :param mock_input: Мок создания входного файла FFmpeg
    :param mock_norm: мок нормализации файлов,
    :param mock_run: мок выполнения команды FFmpeg
    :param tmpdir: временная директория
    """
    mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
    mock_norm.return_value = ["norm1.mp3", "norm2.mp3"]

    def fake_create_ffmpeg_input_file(files, input_file=None):
        path = os.path.join(str(tmpdir), "input.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write('file "norm.mp3"\n')
        return path

    mock_input.side_effect = fake_create_ffmpeg_input_file

    file1 = tmpdir.mkdir("upload").join("file1.mp3")
    file2 = tmpdir.mkdir("upload2").join("file2.mp3")
    file1.write("dummy")
    file2.write("dummy")
    merged_folder = tmpdir.mkdir("merged")
    result = merge_mp3_files_ffmpeg([str(file1), str(file2)], files_count=1, merged_folder=str(merged_folder))
    assert len(result) == 2
    assert mock_run.call_count == 2


@patch.object(Merge, "_normalize_mp3_file")
def test_normalize_mp3_file_parallel(mock_normalize, tmpdir):
    """
    Проверяет параллельную нормализацию MP3-файлов.

    :param mock_normalize: Мок внутренней функции нормализации
    :param tmpdir: временная директория
    """
    mock_normalize.return_value = "normalized_file.mp3"

    file1 = tmpdir.join("file1.mp3")
    file1.write("dummy")

    result = Merge.normalize_mp3_file_parallel([str(file1)], merged_folder=str(tmpdir))
    assert result == ["normalized_file.mp3"]
