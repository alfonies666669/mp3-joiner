import re
import os
import logging
import subprocess
import unicodedata
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Merge:

    @staticmethod
    def _normalize_mp3_file(input_file: str, output_file: str, sample_rate: int, bit_rate: int, channels: int):
        command = [
            'ffmpeg',
            '-i', input_file,
            '-ar', str(sample_rate),
            '-ab', f'{bit_rate}k',
            '-ac', str(channels),
            '-c:a', 'libmp3lame',
            output_file
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            logger.error(result.stderr.decode('utf-8'))
            return None
        return output_file

    @staticmethod
    def create_ffmpeg_input_file(file_paths, input_file='input.txt'):
        with open(input_file, 'w') as f:
            for path in file_paths:
                f.write(f"file '{path}'\n")
        return input_file

    @staticmethod
    def merge_strings(strings: list, count: int) -> list:
        merged = []
        for i in range(0, len(strings), count):
            merged.append(' '.join(strings[i:i + count]))
        return merged

    @staticmethod
    def normalize_mp3_file_parallel(files: list, merged_folder: str, sample_rate: int = 44100, bit_rate: int = 192,
                                    channels: int = 2) -> list:
        normalized_files = [None] * len(files)
        with ThreadPoolExecutor() as executor:
            futures = []
            for idx, file in enumerate(files):
                normalized_file = os.path.join(merged_folder, f'normalized_{os.path.basename(file)}')
                futures.append(executor.submit(Merge._normalize_mp3_file, file, normalized_file,
                                               sample_rate, bit_rate,
                                               channels))
                futures[-1].file_index = idx
            for future in as_completed(futures):
                normalized_file = future.result()
                if normalized_file:
                    normalized_files[future.file_index] = normalized_file
        return normalized_files

    @staticmethod
    def normalize_filename(filename: str) -> str:
        filename = unicodedata.normalize("NFKC", filename)
        filename = re.sub(r'[^\w\s.-]', '', filename, flags=re.UNICODE)
        filename = filename.strip().replace(" ", "_")
        return filename

    @staticmethod
    def save_single_file(file, upload_folder: str, idx: int) -> str:
        safe_filename = Merge.normalize_filename(file.filename)
        if not safe_filename:
            safe_filename = f"file_{idx}.mp3"
        file_path = Path(upload_folder) / safe_filename
        file.save(str(file_path))
        return str(file_path)
