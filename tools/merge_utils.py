import re
import os
import json
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
        return filename.strip().replace(" ", "_")

    @staticmethod
    def save_single_file(file, upload_folder: str, idx: int) -> str:
        safe_filename = Merge.normalize_filename(file.filename)
        if not safe_filename:
            safe_filename = f"file_{idx}.mp3"
        file_path = Path(upload_folder) / safe_filename
        file.save(str(file_path))
        return str(file_path)

    @staticmethod
    def _get_audio_info(file_path):
        command = [
            'ffprobe',
            '-loglevel', 'error',
            '-show_streams',
            '-select_streams', 'a:0',
            '-of', 'json',
            file_path
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            raise RuntimeError(f"FFprobe error: {result.stderr.decode('utf-8')}")
        info = json.loads(result.stdout)
        audio_stream = info['streams'][0]
        return {
            'bitrate': int(audio_stream.get('bit_rate', 0)),
            'sample_rate': int(audio_stream.get('sample_rate', 0)),
            'channels': int(audio_stream.get('channels', 0))
        }

    @staticmethod
    def are_mp3_files_identical_format(file_paths):
        if not file_paths or len(file_paths) < 2:
            return True
        with ThreadPoolExecutor() as executor:
            formats = list(executor.map(Merge._get_audio_info, file_paths))
        formats = [f for f in formats if f is not None]
        if not formats:
            return False
        reference_format = formats[0]
        for fmt in formats[1:]:
            if fmt != reference_format:
                return False
        return True
