# AGENTS.md

## Project

This is a Flask-based MP3 Joiner app.

The app allows users to upload MP3 files, merge them using FFmpeg, and download the result.

## Engineering principles

- Prefer small, reviewable pull requests.
- Do not rewrite the whole project unless explicitly asked.
- Preserve existing behavior unless the task says otherwise.
- Keep Flask routes thin.
- Put file-processing logic into dedicated modules.
- Keep FFmpeg command construction isolated and testable.
- Keep validation logic reusable and tested.
- Avoid adding new dependencies without explaining why.
- Do not commit uploaded files, generated audio files, local temp files, secrets, or environment-specific artifacts.

## Safety rules

Pay special attention to:

- unsafe filenames;
- path traversal;
- unbounded uploads;
- unsupported file extensions;
- corrupt MP3 files;
- FFmpeg failures;
- temporary file cleanup;
- subprocess command safety.

## Testing

After code changes, run:

```bash
pytest
