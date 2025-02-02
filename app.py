import os
import shutil
import tempfile
from flask_compress import Compress
from concurrent.futures import ProcessPoolExecutor
from tools.utils import saving_files_parallel, merge_mp3_files_ffmpeg, create_zip, logger
from flask import Flask, request, jsonify, send_file, render_template, after_this_request

app = Flask(__name__)
Compress(app)
executor = ProcessPoolExecutor()
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
        "error": f"The total file size is too large (>{MAX_CONTENT_LENGTH} MB). "
                 f"Please reduce the number of files or their sizes."
    }), 413


@app.route('/merge', methods=['POST'])
def merge_files():
    files = request.files.getlist('files')
    count = request.form.get('count', type=int)

    if not files or count is None:
        error = 'Files or count not provided'
        logger.error(error)
        return jsonify({'error': error}), 400

    invalid_files = [file.filename for file in files if file.mimetype != 'audio/mpeg']
    if invalid_files:
        logger.error(f"Invalid file types: {invalid_files}")
        return jsonify({'error': 'Only MP3 files are allowed'}), 400

    try:
        upload_folder = tempfile.mkdtemp()
        merged_folder = tempfile.mkdtemp()
        archive_path = os.path.join(merged_folder, 'merged_files.zip')
        file_paths = saving_files_parallel(upload_folder, files)
        merge_future = executor.submit(merge_mp3_files_ffmpeg, file_paths, count, merged_folder)
        merged_files = merge_future.result()
        zip_future = executor.submit(create_zip, archive_path, merged_files)
        final_zip = zip_future.result()
        logger.info("Files merged and archived successfully")

        @after_this_request
        def cleanup(response):
            try:
                shutil.rmtree(upload_folder)
                shutil.rmtree(merged_folder)
            except Exception as E:
                logger.error(f"Error during cleanup: {E}")
            return response

        return send_file(final_zip, as_attachment=True)

    except Exception as e:
        logger.error(f"Error during merging files: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
