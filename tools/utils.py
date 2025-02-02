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
