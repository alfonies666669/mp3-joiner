FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD curl -fsS http://127.0.0.1:5001/healthz || exit 1

EXPOSE 5001
CMD ["gunicorn", "--workers", "2", "--threads", "2", "--timeout", "300", "--bind", "0.0.0.0:5001", "app:app"]
