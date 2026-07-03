# AGENTS.md

## Project

This is a Flask-based MP3 Joiner app.

The app allows users to upload MP3 files, merge them using FFmpeg, and download the result as a ZIP archive.

## Engineering Principles

- Prefer small, reviewable pull requests.
- Do not rewrite the whole project unless explicitly asked.
- Preserve existing behavior unless the task says otherwise.
- Keep Flask routes thin.
- Put file-processing logic into dedicated modules.
- Keep FFmpeg command construction isolated and testable.
- Keep validation logic reusable and tested.
- Avoid adding new dependencies without explaining why.
- Do not commit uploaded files, generated audio files, local temp files, logs, secrets, `.env`, caches, or virtualenvs.

## Repo Map

- `app.py`: Flask app, routes, environment config, request orchestration.
- `tools/validation.py`: upload, count, size, extension, and MP3 validation.
- `tools/security.py`: CSRF, same-origin, and Bearer auth.
- `tools/api_auth.py`: token loading and API auth helpers.
- `tools/merge_utils.py`: filename normalization, MP3 metadata, FFmpeg calls, and merge logic.
- `tools/utils.py`: file saving, MP3 stream validation, ZIP creation, and related helpers.
- `logger/logger.py`: application and user logging.
- `tests/`: pytest suite.

## Safety Rules

Pay special attention to:

- unsafe filenames;
- path traversal;
- unbounded uploads;
- unsupported file extensions;
- corrupt MP3 files;
- FFmpeg failures;
- subprocess timeouts;
- temporary file cleanup;
- subprocess command safety;
- CSRF and Bearer auth behavior.

## Testing

After code changes, run the smallest relevant test command first:

```bash
pytest -q
```

Before a pull request, run the broader checks if available:

```bash
pytest
black --check tools tests app.py
isort --check-only tools tests app.py
ruff check .
ruff format --check .
pylint app.py tools logger tests --jobs=2
```

## Run App

For local development:

```bash
API_TOKENS_REQUIRED=false make run
```

The app should listen on:

```text
http://127.0.0.1:5001
```

## Codex Workflow

For non-trivial tasks, Codex should:

1. inspect the relevant files first;
2. explain the current behavior;
3. propose a short plan;
4. list files it intends to modify;
5. make the smallest safe diff;
6. run the smallest relevant tests;
7. summarize changes, tests run, and remaining risks.

Do not perform opportunistic refactors unless explicitly requested.
