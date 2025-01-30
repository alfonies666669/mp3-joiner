import os
import uuid
from flask_compress import Compress
from flask import Flask, request, jsonify, send_file, render_template, after_this_request
from tools.utils import saving_files, merge_mp3_files_ffmpeg, create_zip, remove_folder, logger

app = Flask(__name__)
Compress(app)

BASE_UPLOAD_FOLDER = os.getenv('BASE_UPLOAD_FOLDER', 'uploads')
BASE_MERGED_FOLDER = os.getenv('BASE_MERGED_FOLDER', 'merged')
MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 500 * 1024 * 1024))

os.makedirs(BASE_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(BASE_MERGED_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = BASE_UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH


@app.route('/')
def index():
    return render_template('index.html')


@app.errorhandler(413)
def request_entity_too_large(error):
    remove_folder([BASE_UPLOAD_FOLDER, BASE_MERGED_FOLDER])
    logger.error("Request entity too large")
    return jsonify({
        "error": "The total file size is too large (>500 MB). Please reduce the number of files or their sizes."
    }), 413


@app.route('/merge', methods=['POST'])
def merge_files():
    files = request.files.getlist('files')
    count = request.form.get('count', type=int)
    if not files or count is None:
        logger.error("Files or count not provided")
        return jsonify({'error': 'Files or count not provided'}), 400

    for file in files:
        if file.mimetype != 'audio/mpeg':
            logger.error(f"Invalid file type: {file.filename}")
            return jsonify({'error': 'Only MP3 files are allowed'}), 400

    unique_id = str(uuid.uuid4())
    upload_folder = os.path.join(BASE_UPLOAD_FOLDER, unique_id)
    merged_folder = os.path.join(BASE_MERGED_FOLDER, unique_id)

    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(merged_folder, exist_ok=True)

    file_paths = saving_files(upload_folder, files)
    merged_files = merge_mp3_files_ffmpeg(file_paths, count, merged_folder=merged_folder)
    archive_path = create_zip(merged_folder, merged_files)

    @after_this_request
    def cleanup_files(response):
        remove_folder([upload_folder, merged_folder])
        return response

    logger.info("Files merged successfully")
    return send_file(archive_path, as_attachment=True)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
