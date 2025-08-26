"""
Модуль с утилитами для работы с файлами: сохранение, объединение и архивирование.
"""

import os
from zipfile import ZipFile

from mutagen.mp3 import MP3, HeaderNotFoundError

from logger.logger import app_logger

from tools.merge_utils import Merge


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
        except HeaderNotFoundError as e:
            app_logger.error("Corrupt or invalid MP3: %s", file.filename)
            app_logger.error("Exception: %s", e)
            return {"error": f"File {file.filename} is not a valid MP3"}, 400
        except Exception as e:
            # Иногда могут быть другие ошибки. Логируем и возвращаем 400, но не глушим всё.
            app_logger.error("Unexpected error while checking MP3 file %s: %s", file.filename, e)
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
            app_logger.error("Ошибка при сохранении %s: %s", file.filename, e)
            raise RuntimeError(f"Ошибка при сохранении {file.filename}: {e}") from e
    return file_paths


def smart_merge_mp3_files(file_paths: list, files_count: int, merged_folder: str) -> list[str]:
    """
    Интеллектуальное объединение MP3:
    Если параметры одинаковые — просто байтовый merge (молниеносно).
    Если разные — нормализация через ffmpeg, потом merge.
    """
    if Merge.all_params_equal(file_paths):
        return Merge.merge_files_in_groups(file_paths, files_count, merged_folder)
    normalized_files = Merge.normalize_mp3_file_parallel(file_paths, merged_folder)
    return Merge.merge_mp3_groups_ffmpeg(normalized_files, files_count, merged_folder)


def create_zip(merged_folder: str, merged_files: list) -> str:
    """
    Создаёт ZIP-архив с объединёнными файлами.
    Если какой-то файл отсутствует, пишет warning в лог.
    Если список файлов пуст — кидает RuntimeError.
    :param merged_folder: Директория, в которой будет создан архив.
    :param merged_files: Список файлов для добавления в архив.
    :return: Путь к созданному ZIP-файлу.
    """
    archive_path = os.path.join(merged_folder, "merged_files.zip")
    if not merged_files:
        msg = "Нет файлов для архивации."
        app_logger.error(msg)
        raise RuntimeError(msg)
    with ZipFile(archive_path, "w") as zipf:
        for merged_file in merged_files:
            if os.path.isfile(merged_file):
                zipf.write(str(merged_file), os.path.basename(merged_file))
            else:
                app_logger.warning("Файл %s не найден, не добавлен в архив.", merged_file)
    app_logger.info("Создан архив: %s", archive_path)
    return archive_path
