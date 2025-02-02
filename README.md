# MP3 Joiner

**MP3 Joiner** is a simple web application that allows you to merge multiple MP3 files into a single file. Built using
Python and Flask, the app also utilizes FFmpeg for audio processing.

---

## Features

- Upload multiple MP3 files for merging.
- Specify the number of files to merge in one group.
- Download the merged files as a ZIP archive.
- Clean and intuitive user interface.

---

## Technologies Used

- **Python 3**
- **Flask 2.0.3**
- **Werkzeug 2.0.3**
- **FFmpeg**
- HTML, CSS (Bootstrap)

---

## Installation

### Prerequisites

- Python 3.x installed.
- FFmpeg installed on your system.
- [Git](https://git-scm.com/) installed.

### Steps

1. Clone the repository:
   ```bash
   git clone https://github.com/alfonies666669/mp3-joiner.git
   cd mp3-joiner
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python app.py
   ```

4. Open your browser and navigate to:
   ```
   http://127.0.0.1:5001
   ```

---

## Docker Deployment

You can deploy the application using Docker.

### Steps

1. Build the Docker image:
   ```bash
   docker build -t mp3-joiner .
   ```

2. Run the Docker container:
   ```bash
   docker run -p 5001:5001 mp3-joiner
   ```

3. Access the application at:
   ```
   http://localhost:5001
   ```

---

## Usage

1. Navigate to the homepage.
2. Upload the MP3 files you want to merge.
3. Specify the number of files to merge per group.
4. Click the "Merge Files" button.
5. Download the resulting ZIP archive with the merged files.

---

## Roadmap

- Add support for additional audio formats.
- Improve error handling and validation.
- Add user authentication for managing files.
- Implement progress indicators for large uploads.

---

## Contributing

Contributions are welcome! Feel free to submit a pull request or open an issue to report bugs or suggest new features.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## Acknowledgements

- [Flask Documentation](https://flask.palletsprojects.com/)
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)

---

## Live Demo

Once deployed, the live version will be available here:
https://santscho6666.pythonanywhere.com