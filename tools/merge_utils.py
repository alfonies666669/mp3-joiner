"""
Модуль, содержащий утилиты для обработки и объединения MP3-файлов.
"""

import os
import re
import logging
import tempfile
import subprocess
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed

from mutagen.mp3 import MP3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Merge:
    """
    Класс, предоставляющий статические методы для нормализации и объединения MP3-файлов.
    """

    @staticmethod
    def _get_mp3_params(file_path: str) -> tuple:
        audio = MP3(file_path)
        return audio.info.bitrate, audio.info.sample_rate, audio.info.channels

    @staticmethod
    def all_params_equal(files: list) -> bool:
        params = [Merge._get_mp3_params(f) for f in files]
        return all(p == params[0] for p in params)

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

    @staticmethod
    def normalize_mp3_file_parallel(
        files: list, merged_folder: str, sample_rate: int = 44100, bit_rate: int = 192, channels: int = 2
    ) -> list:
        """
        Параллельно нормализует несколько аудиофайлов.
        Возвращает список нормализованных файлов (с сохранением исходного порядка!).
        """
        os.makedirs(merged_folder, exist_ok=True)
        normalized_files = [None] * len(files)

        def normalize_one(file_path, idx):
            output_path = os.path.join(merged_folder, f"normalized_{os.path.basename(file_path)}")
            command = [
                "ffmpeg",
                "-i",
                file_path,
                "-ar",
                str(sample_rate),
                "-ab",
                f"{bit_rate}k",
                "-ac",
                str(channels),
                "-c:a",
                "libmp3lame",
                output_path,
                "-y",
            ]
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0:
                logger.error(f"[normalize_mp3] Error for {file_path}: {result.stderr.decode('utf-8')}")
                return idx, None
            return idx, output_path

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(normalize_one, file_path, idx) for idx, file_path in enumerate(files)]
            for future in as_completed(futures):
                idx, result = future.result()
                if result:
                    normalized_files[idx] = result
                else:
                    logger.error(f"Normalization failed for {files[idx]}")
        if any(f is None for f in normalized_files):
            logger.error(f"Normalized only {sum(f is not None for f in normalized_files)} of {len(files)} files.")

        return normalized_files

    @staticmethod
    def merge_files_in_groups(file_list: list[str], group_size: int, output_folder: str) -> list[str]:
        """
        Объединяет файлы из списка по группам заданного размера побайтово.
        *Объединение работает корректно только с файлами, имеющими одинаковые х-ки.
        :param file_list: Список путей к исходным файлам.
        :param group_size: Количество файлов в группе для объединения.
        :param output_folder: Папка, куда будут сохранены объединённые файлы.
        :return: Список путей к объединённым файлам.
        """
        os.makedirs(output_folder, exist_ok=True)
        merged_paths = []
        for idx, start in enumerate(range(0, len(file_list), group_size), start=1):
            group = file_list[start : start + group_size]
            output_path = os.path.join(output_folder, f"merged_{idx}.mp3")
            with open(output_path, "wb") as out_f:
                for file_path in group:
                    if not os.path.isfile(file_path):
                        print(f"Warning: File '{file_path}' does not exist, skipping.")
                        continue
                    with open(file_path, "rb") as in_f:
                        for chunk in iter(lambda: in_f.read(1024 * 1024), b""):
                            out_f.write(chunk)
            merged_paths.append(output_path)
        return merged_paths

    @staticmethod
    def merge_mp3_groups_ffmpeg(file_list, group_size, output_folder) -> list:
        """
        Объединяет mp3-файлы в группы по group_size через ffmpeg concat.
        Возвращает список путей к полученным файлам.
        """
        os.makedirs(output_folder, exist_ok=True)
        merged_paths = []
        for idx, start in enumerate(range(0, len(file_list), group_size), start=1):
            group = file_list[start : start + group_size]
            output_path = os.path.join(output_folder, f"merged_{idx}.mp3")
            with tempfile.NamedTemporaryFile("w", delete=False) as f:
                for path in group:
                    f.write(f"file '{path}'\n")
                list_path = f.name
            try:
                command = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", output_path]
                result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if result.returncode != 0:
                    logger.error(f"FFmpeg error for group {idx}:")
                    logger.error(result.stderr.decode())
                    continue
                merged_paths.append(output_path)
            finally:
                os.remove(list_path)
        return merged_paths
