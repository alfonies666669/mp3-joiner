import shutil
from zipfile import ZipFile
from tools.merge_utils import *


def saving_files(upload_folder, files, secure_filename):
    file_paths = []
    for file in files:
        filename = secure_filename(file.filename)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        file_paths.append(file_path)
    return file_paths


def merge_mp3_files_ffmpeg(file_paths, files_count, merged_folder):
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
            print(result.stderr.decode('utf-8'))
            continue
        merged_files.append(output_path)
    return merged_files


def create_zip(merged_folder, merged_files):
    archive_path = os.path.join(merged_folder, 'merged_files.zip')
    with ZipFile(archive_path, 'w') as zipf:
        for merged_file in merged_files:
            zipf.write(str(merged_file), os.path.basename(merged_file))
    return archive_path


def remove_folder(folder_path):
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
    else:
        print(f"Folder '{folder_path}' does not exist.")
