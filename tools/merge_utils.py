"""
Модуль, содержащий утилиты для обработки и объединения MP3-файлов.
"""

import os
import re
import logging
import subprocess
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Merge:
    """
    Класс, предоставляющий статические методы для нормализации и объединения MP3-файлов.
    """

    @staticmethod
    def _normalize_mp3_file(
        input_file: str,
        output_file: str,
        sample_rate: int,
        bit_rate: int,
        channels: int,
    ) -> str | None:
        """
        Нормализует один аудиофайл с помощью FFmpeg.

        :param input_file: Путь к исходному файлу,
        :param output_file: путь к выходному файлу
        :param sample_rate: частота дискретизации
        :param bit_rate: битрейт
        :param channels: количество каналов
        :return: путь к выходному файлу или None при ошибке
        """
        command = [
            "ffmpeg",
            "-i",
            input_file,
            "-ar",
            str(sample_rate),
            "-ab",
            f"{bit_rate}k",
            "-ac",
            str(channels),
            "-c:a",
            "libmp3lame",
            output_file,
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if result.returncode != 0:
            logger.error(result.stderr.decode("utf-8"))
            return None
        return output_file

    @staticmethod
    def create_ffmpeg_input_file(file_paths, input_file="input.txt") -> str:
        """
        Создаёт временный файл с путями входных файлов для FFmpeg.

        :param file_paths: Список путей к файлам
        :param input_file: имя временного файла
        :return: путь к созданному файлу
        """
        with open(input_file, "w", encoding="utf-8") as f:
            for path in file_paths:
                f.write(f"file '{path}'\n")
        return input_file

    @staticmethod
    def merge_strings(strings: list, count: int) -> list:
        """
        Разбивает список строк на подгруппы по заданному количеству элементов.

        :param strings: Список строк,
        :param count: максимальное количество элементов в группе,
        :return: список списков строк
        """
        merged = []
        for i in range(0, len(strings), count):
            merged.append(" ".join(strings[i : i + count]))
        return merged

    @staticmethod
    def normalize_mp3_file_parallel(
        files: list,
        merged_folder: str,
        sample_rate: int = 44100,
        bit_rate: int = 192,
        channels: int = 2,
    ) -> list:
        """
        Параллельно нормализует несколько аудиофайлов.

        :param files: Список путей к исходным файлам,
        :param merged_folder: директория для сохранения результатов,
        :param sample_rate: частота дискретизации,
        :param bit_rate: битрейт,
        :param channels: количество каналов,
        :return: список путей к нормализованным файлам.
        """
        normalized_files = [None] * len(files)
        with ThreadPoolExecutor() as executor:
            futures = []
            for idx, file in enumerate(files):
                normalized_file = os.path.join(merged_folder, f"normalized_{os.path.basename(file)}")
                futures.append(
                    executor.submit(
                        Merge._normalize_mp3_file,
                        file,
                        normalized_file,
                        sample_rate,
                        bit_rate,
                        channels,
                    )
                )
                futures[-1].file_index = idx
            for future in as_completed(futures):
                normalized_file = future.result()
                if normalized_file:
                    normalized_files[future.file_index] = normalized_file
        return normalized_files

    @staticmethod
    def normalize_filename(filename: str) -> str:
        """
        Приводит имя файла к безопасному формату.

        :param filename: Исходное имя файла
        :return: нормализованное имя файла
        """
        filename = unicodedata.normalize("NFKC", filename)
        filename = re.sub(r"[^\w\s.-]", "", filename, flags=re.UNICODE)
        filename = filename.strip()
        filename = re.sub(r"\s+", "_", filename)
        filename = re.sub(r"_+\.", ".", filename)
        filename = re.sub(r"_+$", "", filename)
        filename = re.sub(r"^\.+", "", filename)
        filename = re.sub(r"\.+$", "", filename)
        filename = re.sub(r"__+", "_", filename)
        return filename
