import os
import tempfile
from flask_compress import Compress
from flask import Flask, request, jsonify, send_file, render_template
from tools.utils import saving_files, merge_mp3_files_ffmpeg, create_zip, logger

app = Flask(__name__)
Compress(app)

MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 100 * 1024 * 1024))
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/how-it-works')
def how_it_works():
    return render_template('how-it-works.html')


@app.errorhandler(413)
def request_entity_too_large(error):
    logger.error("Request entity too large")
    return jsonify({
        "error": "The total file size is too large (>100 MB). Please reduce the number of files or their sizes."
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

    with tempfile.TemporaryDirectory() as upload_folder, tempfile.TemporaryDirectory() as merged_folder:
        file_paths = saving_files(upload_folder, files)
        merged_files = merge_mp3_files_ffmpeg(file_paths, count, merged_folder=merged_folder)
        archive_path = create_zip(merged_folder, merged_files)
        logger.info("Files merged successfully")
        return send_file(archive_path, as_attachment=True)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
