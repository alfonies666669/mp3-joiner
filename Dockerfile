FROM python:3.10-slim

RUN apt-get update && apt-get install -y ffmpeg=7:4.4.2-0ubuntu0.22.04.1 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "app.py"]