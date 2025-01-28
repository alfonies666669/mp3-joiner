import os
import uuid
from werkzeug.utils import secure_filename
from tools.utils import saving_files, merge_mp3_files_ffmpeg, create_zip, remove_folder
from flask import Flask, request, jsonify, send_file, render_template, after_this_request

app = Flask(__name__)

BASE_UPLOAD_FOLDER = 'uploads'
BASE_MERGED_FOLDER = 'merged'

os.makedirs(BASE_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(BASE_MERGED_FOLDER, exist_ok=True)

unique_id = str(uuid.uuid4())
UPLOAD_FOLDER = os.path.join(BASE_UPLOAD_FOLDER, unique_id)
MERGED_FOLDER = os.path.join(BASE_MERGED_FOLDER, unique_id)

app.config['UPLOAD_FOLDER'] = BASE_UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024


@app.route('/')
def index():
    return render_template('index.html')


@app.errorhandler(413)
def request_entity_too_large(error):
    remove_folder(UPLOAD_FOLDER)
    remove_folder(MERGED_FOLDER)
    return jsonify({
        "error": "The total file size is too large (>500 MB). Please reduce the number of files or their sizes."
    }), 413


@app.route('/merge', methods=['POST'])
def merge_files():
    files = request.files.getlist('files')
    count = request.form.get('count', type=int)

    if not files or count is None:
        return jsonify({'error': 'Files or count not provided'}), 400
    for file in files:
        if file.mimetype != 'audio/mpeg':
            return jsonify({'error': 'Only MP3 files are allowed'}), 400

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(MERGED_FOLDER, exist_ok=True)

    file_paths = saving_files(UPLOAD_FOLDER, files, secure_filename)

    merged_files = merge_mp3_files_ffmpeg(file_paths, count, merged_folder=MERGED_FOLDER)

    archive_path = create_zip(MERGED_FOLDER, merged_files)

    @after_this_request
    def cleanup_files(response):
        remove_folder(UPLOAD_FOLDER)
        remove_folder(MERGED_FOLDER)
        return response

    return send_file(archive_path, as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
