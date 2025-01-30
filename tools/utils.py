import shutil
from zipfile import ZipFile
from tools.merge_utils import *


def saving_files(upload_folder: str, files: list) -> list:
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
    normalize_files = Merge.normalize_mp3_file_parallel(file_paths, merged_folder)
    merged_list = Merge.merge_strings(normalize_files, files_count)
    merged_files = []
    for idx, files_str in enumerate(merged_list):
        files = files_str.split()
        input_file = Merge.create_ffmpeg_input_file(files)
        output_path = os.path.join(merged_folder, f'merged_file_{idx + 1}.mp3')
        command = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', input_file, '-c', 'copy', output_path]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        os.remove(input_file)
        if result.returncode != 0:
            logger.error(result.stderr.decode('utf-8'))
            continue
        merged_files.append(output_path)
    return merged_files


def create_zip(merged_folder: str, merged_files: list) -> str:
    archive_path = os.path.join(merged_folder, 'merged_files.zip')
    with ZipFile(archive_path, 'w') as zipf:
        for merged_file in merged_files:
            zipf.write(str(merged_file), os.path.basename(merged_file))
    return archive_path


def _remove(folder_path: str):
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
    else:
        logger.error(f"Folder '{folder_path}' does not exist.")


def remove_folder(folder_paths: str | list[str]):
    if isinstance(folder_paths, list):
        for folder in folder_paths:
            _remove(folder)
    else:
        _remove(folder_paths)
