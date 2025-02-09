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


def create_zip(archive_path: str, merged_files: list):
    with ZipFile(archive_path, 'a') as zipf:
        for merged_file in merged_files:
            zipf.write(merged_file, os.path.basename(merged_file))
    return archive_path


def merge_mp3(file_paths: list, files_count: int, merged_folder: str):
    same_format = Merge.are_mp3_files_identical_format(file_paths)
    normalize_files = file_paths if same_format else Merge.normalize_mp3_file_parallel(file_paths, merged_folder)
    mp3_without_tags = []
    for idx, i in enumerate(normalize_files):
        mp3_without_tags.append(Merge.clean_mp3(i, os.path.join(merged_folder, f'tags_none_{idx}.mp3')))
    merged_list = Merge.merge_strings(mp3_without_tags, files_count)
    for idx, merge_string in enumerate(merged_list):
        output_path = os.path.join(merged_folder, f'merged_{idx + 1}.mp3')
        try:
            merged_command = f'cat {merge_string} > {output_path}'
            subprocess.run(merged_command, shell=True, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Ошибка при выполнении команды cat: {e}")
