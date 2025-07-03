"""
Модуль с утилитами для работы с файлами: сохранение, объединение и архивирование.
"""

import os
from zipfile import ZipFile

from mutagen.mp3 import MP3

from tools.merge_utils import Merge, logger


def check_files_are_mp3(files) -> None | tuple:
    """
    Проверяет, что каждый файл из списка реально является mp3-файлом.
    :param files: Список FileStorage объектов
    :return: None если всё ок, иначе (dict, int) для Flask
    """
    for file in files:
        file.stream.seek(0)
        try:
            MP3(file.stream)
            file.stream.seek(0)
        except Exception as e:
            if logger:
                logger.error(f"Corrupt or invalid MP3: {file.filename}")
                logger.error(f"Exception: {e}")
            return {"error": f"File {file.filename} is not a valid MP3"}, 400
    return None


def saving_files(upload_folder: str, files: list) -> list:
    """
    Сохраняет загруженные файлы в указанной директории с безопасными именами.
    """
    file_paths = []
    for idx, file in enumerate(files, start=1):
        safe_name = Merge.normalize_filename(file.filename) or f"file_{idx}.mp3"
        path = os.path.join(upload_folder, safe_name)
        try:
            file.save(path)
            file_paths.append(path)
        except Exception as e:
            logger.error(f"Ошибка при сохранении {file.filename}: {e}")
            raise RuntimeError(f"Ошибка при сохранении {file.filename}: {e}")
    return file_paths


def smart_merge_mp3_files(file_paths: list, files_count: int, merged_folder: str) -> list[str]:
    """
    Интеллектуальное объединение MP3:
    Если параметры одинаковые — просто байтовый merge (молниеносно).
    Если разные — нормализация через ffmpeg, потом merge.
    """
    if Merge.all_params_equal(file_paths):
        return Merge.merge_files_in_groups(file_paths, files_count, merged_folder)
    else:
        normalized_files = Merge.normalize_mp3_file_parallel(file_paths, merged_folder)
        return Merge.merge_mp3_groups_ffmpeg(normalized_files, files_count, merged_folder)


def create_zip(merged_folder: str, merged_files: list) -> str:
    """
    Создаёт ZIP-архив с объединёнными файлами.
    Если какой-то файл отсутствует, пишет warning в лог (или stdout).
    Если список файлов пуст — кидает RuntimeError.
    :param merged_folder: Директория, в которой будет создан архив.
    :param merged_files: Список файлов для добавления в архив.
    :return: Путь к созданному ZIP-файлу.
    """
    archive_path = os.path.join(merged_folder, "merged_files.zip")
    if not merged_files:
        msg = "Нет файлов для архивации."
        if logger:
            logger.error(msg)
        raise RuntimeError(msg)
    with ZipFile(archive_path, "w") as zipf:
        for merged_file in merged_files:
            if os.path.isfile(merged_file):
                zipf.write(str(merged_file), os.path.basename(merged_file))
            else:
                warning_msg = f"Файл {merged_file} не найден, не добавлен в архив."
                logger.warning(warning_msg)
    logger.info(f"Создан архив: {archive_path}")
    return archive_path
