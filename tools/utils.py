from zipfile import ZipFile
from tools.merge_utils import *


def saving_files_parallel(upload_folder: str, files: list) -> list:
    with ThreadPoolExecutor() as executor:
        results = executor.map(
            Merge.save_single_file,
            files,
            [upload_folder] * len(files),
            range(1, len(files) + 1)
        )
    return list(results)


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


def create_zip(archive_path: str, merged_files: list):
    with ZipFile(archive_path, 'a') as zipf:
        for merged_file in merged_files:
            zipf.write(merged_file, os.path.basename(merged_file))
    return archive_path


def merge_mp3_files_memory(merged_list: list, merged_folder: str) -> list:
    merged_files = []
    for cnt, group in enumerate(merged_list):
        merged_filename = os.path.join(merged_folder, f'Merged_{cnt + 1}.mp3')
        # Используем буфер памяти (RAM), чтобы избежать лишней записи на диск
        with open(merged_filename, 'wb') as output_file:
            for file_path in group:
                with open(file_path, 'rb') as input_file:
                    output_file.write(input_file.read())  # Читаем и записываем напрямую
        merged_files.append(merged_filename)
    return merged_files


def merge_mp3_parallel(file_paths: list, files_count: int, merged_folder: str) -> list:
    same_format = Merge.are_mp3_files_identical_format(file_paths)
    merged_list = Merge.merge_strings(
        file_paths if same_format else Merge.normalize_mp3_file_parallel(file_paths, merged_folder), files_count)
    return merge_mp3_files_memory(merged_list=merged_list, merged_folder=merged_folder)
