FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LOG_DIR=/var/logs/mp3_joiner \
    USER_LOG_PATH=/var/logs/mp3_joiner \
    TOKEN_FILE_PATH=/app/tokens/allowed_tokens.txt \
    API_TOKENS_REQUIRED=true \
    GEO_LOOKUP_ENABLED=false

RUN useradd -m -u 10001 appuser

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /var/logs/mp3_joiner /app/tokens \
    && chown -R appuser:appuser /var/logs/mp3_joiner /app

USER appuser

EXPOSE 5001
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -fsS http://127.0.0.1:5001/healthz || exit 1

CMD ["gunicorn", "--workers", "2", "--threads", "2", "--timeout", "300", "--bind", "0.0.0.0:5001", "app:app"]
