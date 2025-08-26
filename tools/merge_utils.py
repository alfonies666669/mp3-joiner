"""Модуль для нормализации и объединения MP3-файлов"""

import os
import re
import tempfile
import subprocess
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed

from mutagen.mp3 import MP3

from logger.logger import app_logger


class Merge:
    """
    Класс, предоставляющий статические методы для нормализации и объединения MP3-файлов.
    """

    @staticmethod
    def _get_mp3_params(file_path: str) -> tuple:
        """
        Возвращает параметры MP3-файла (bitrate, sample_rate, channels).
        """
        try:
            audio = MP3(file_path)
            # Безопасно берем значения, если нет — ставим None
            bitrate = getattr(audio.info, "bitrate", None)
            sample_rate = getattr(audio.info, "sample_rate", None)
            channels = getattr(audio.info, "channels", None)
            return bitrate, sample_rate, channels
        except Exception as e:
            app_logger.error("Failed to get MP3 params for %s: %s", file_path, e)
            return None, None, None

    @staticmethod
    def all_params_equal(files: list) -> bool:
        """
        Проверяет, одинаковы ли параметры у всех файлов.
        """
        params = [Merge._get_mp3_params(f) for f in files]
        return all(p == params[0] for p in params)

    @staticmethod
    def normalize_filename(filename: str) -> str:
        """
        Приводит имя файла к безопасному формату.
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
        filename = re.sub(r"\.{2,}(\.[A-Za-z0-9]{1,5})$", r"\1", filename)
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
            result = subprocess.run(command, capture_output=True, check=False)
            if result.returncode != 0:
                app_logger.error("[normalize_mp3] Error for %s: %s", file_path, result.stderr.decode("utf-8"))
                return idx, None
            return idx, output_path

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(normalize_one, file_path, idx) for idx, file_path in enumerate(files)]
            for future in as_completed(futures):
                idx, result = future.result()
                if result:
                    normalized_files[idx] = result
                else:
                    app_logger.error("Normalization failed for %s", files[idx])
        if any(f is None for f in normalized_files):
            app_logger.error(
                "Normalized only %d of %d files.", sum(f is not None for f in normalized_files), len(files)
            )

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
                        app_logger.warning("File '%s' does not exist, skipping.", file_path)
                        continue
                    with open(file_path, "rb") as in_f:
                        while True:
                            chunk = in_f.read(1024 * 1024)
                            if not chunk:
                                break
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
                result = subprocess.run(command, capture_output=True, check=False)
                if result.returncode != 0:
                    app_logger.error("FFmpeg error for group %d: %s", idx, result.stderr.decode())
                    continue
                merged_paths.append(output_path)
            finally:
                os.remove(list_path)
        return merged_paths
