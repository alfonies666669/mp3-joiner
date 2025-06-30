"""
Модуль с утилитами для работы с файлами: сохранение, объединение и архивирование.
"""

import os
import subprocess
from zipfile import ZipFile

from tools.merge_utils import Merge, logger


def saving_files(upload_folder: str, files: list) -> list:
    """
    Сохраняет загруженные файлы в указанной директории с безопасными именами.

    :param upload_folder: Путь к директории для сохранения файлов
    :param files: список загруженных файлов (werkzeug.datastructures.FileStorage)
    :return: список путей к сохранённым файлам
    """
    file_paths = []
    for idx, file in enumerate(files, start=1):
        original_filename = file.filename
        safe_filename = Merge.normalize_filename(original_filename)
        if not safe_filename:
            safe_filename = f"file_{idx}.mp3"
        file_path = os.path.join(upload_folder, safe_filename)
        file.save(file_path)
        file_paths.append(file_path)
    return file_paths


def merge_mp3_files_ffmpeg(file_paths: list, files_count: int, merged_folder: str) -> list:
    """
    Объединяет MP3-файлы через FFmpeg на основе заданного количества файлов на группу.

    :param file_paths: Список путей к исходным файлам
    :param files_count: количество файлов в одной группе
    :param merged_folder: директория для сохранения объединённых файлов
    :return: список путей к объединённым файлам
    """
    normalize_files = Merge.normalize_mp3_file_parallel(file_paths, merged_folder)
    merged_list = Merge.merge_strings(normalize_files, files_count)
    merged_files = []

    for idx, files_str in enumerate(merged_list):
        files = files_str.split()
        input_file = Merge.create_ffmpeg_input_file(files)
        output_path = os.path.join(merged_folder, f"merged_file_{idx + 1}.mp3")
        command = [
            "ffmpeg",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            input_file,
            "-c",
            "copy",
            output_path,
        ]

        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        os.remove(input_file)

        if result.returncode != 0:
            logger.error(result.stderr.decode("utf-8"))
            continue

        merged_files.append(output_path)

    return merged_files


def create_zip(merged_folder: str, merged_files: list) -> str:
    """
    Создаёт ZIP-архив с объединёнными файлами.

    :param merged_folder: Директория, в которой будет создан архив
    :param merged_files: список файлов для добавления в архив
    :return: путь к созданному ZIP-файлу
    """
    archive_path = os.path.join(merged_folder, "merged_files.zip")
    with ZipFile(archive_path, "w") as zipf:
        for merged_file in merged_files:
            zipf.write(str(merged_file), os.path.basename(merged_file))
    return archive_path
