# MP3 Joiner 🎶

[![Latest release](https://img.shields.io/github/v/release/alfonies666669/mp3-joiner?sort=semver)](https://github.com/alfonies666669/mp3-joiner/releases)
[![CI](https://github.com/alfonies666669/mp3-joiner/actions/workflows/ci.yml/badge.svg)](https://github.com/alfonies666669/mp3-joiner/actions/workflows/ci.yml)
[![Deploy](https://github.com/alfonies666669/mp3-joiner/actions/workflows/deploy.yml/badge.svg)](https://github.com/alfonies666669/mp3-joiner/actions/workflows/deploy.yml)
[![Docker](https://img.shields.io/badge/docker-ghcr.io%2Falfonies666669%2Fmp3--joiner-blue)](https://github.com/alfonies666669/mp3-joiner/pkgs/container/mp3-joiner)

**MP3 Joiner** — это production-ready веб-приложение для объединения MP3-файлов.
Написано на **Python (Flask)**, использует **FFmpeg**, упаковано в Docker и раскатывается на VPS через **GitHub Actions
**.

**👉 Live Demo: http://mp3-joiner.ru**
---
👉 [![ReDoc](https://img.shields.io/badge/ReDoc-OpenAPI-red)](https://alfonies666669.github.io/mp3-joiner/) — спецификация для клиентов, Swagger, автотестов.
---

## ✨ Возможности

- Объединение MP3-файлов с сохранением качества.
- Групповое слияние: указываешь `N` — получаешь пачки.
- Результат в ZIP-архиве.
- Чистый и адаптивный интерфейс (Bootstrap).
- Rate limiting (анти-DDoS).
- API-токены + CSRF защита.
- (Опционально) Geo-lookup по IP.
- Healthcheck endpoint `/healthz`.
- Логирование:
    - `app.log` (ротирующий логгер)
    - JSON-логи пользовательских действий.
- CI/CD пайплайн (тесты, линтеры, автодеплой).

---

## 🛠️ Технологии

- **Backend:** Python 3.13, Flask, Gunicorn, FFmpeg
- **Frontend:** HTML5, Bootstrap 5
- **CI/CD:** GitHub Actions (линтеры → тесты → docker build → deploy)
- **Container:** Docker, GitHub Container Registry (GHCR)
- **Infra:** docker-compose + nginx

---

## 🚀 Установка и запуск

### 1. Docker (рекомендуется)

```bash
docker pull ghcr.io/alfonies666669/mp3-joiner:latest

docker run -d \
  -p 5001:5001 \
  -v $(pwd)/logs:/var/logs/mp3_joiner \
  -v $(pwd)/tokens:/app/tokens \
  -e SECRET_KEY=change-me \
  -e ALLOWED_ORIGIN=http://localhost:5001 \
  --name mp3-joiner \
  ghcr.io/alfonies666669/mp3-joiner:latest
```

Перейти на:

   ```
   http://127.0.0.1:5001
   ```

---

### 2. docker-compose.prod.yml

```bash
TAG=latest docker compose -f docker-compose.prod.yml up -d
```

---

### 3. Локально (dev)

```bash
git clone https://github.com/alfonies666669/mp3-joiner.git
cd mp3-joiner
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
make run
```

---

## CI/CD

- CI (ci.yml): pytest + coverage, black + isort + pylint, docker build & smoke test.
- Release Drafter: автогенерация changelog.
- Deploy (deploy.yml):
- Логин в GHCR
- Pull нового образа
- docker compose up -d на VPS
- Любой тег vX.Y.Z = релиз + новый Docker-образ.

---

## Использование

	1.	Перейти на /.
	2.	Загрузить MP3-файлы.
	3.	Указать количество файлов на группу.
	4.	Нажать Merge Files.
	5.	Скачать архив merged_files.zip.

---

## Roadmap

- Поддержка WAV/OGG
- Прогресс-бар загрузки и обработки
- Drag-and-drop интерфейс
- Авторизация (OAuth2)
- Интеграция с облаками (GDrive/YandexDisk)
- E2E-тесты (Playwright)

---

## Contributing

Пулл-реквесты и идеи приветствуются!
Открывайте issue или присылайте свой PR.
---

## License

MIT License — см. [LICENSE](LICENSE).

---

## Acknowledgements

- [Flask Documentation](https://flask.palletsprojects.com/)
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)
- [GitHub Actions](https://docs.github.com/en/actions)
- [Docker](https://docs.docker.com/)

---
