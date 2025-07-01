# MP3 Joiner

**MP3 Joiner** — это веб-приложение для объединения нескольких MP3-файлов в один.
Написано на Python (Flask), использует FFmpeg для обработки аудио и полностью автоматизировано через CI/CD пайплайн.

---

## Features

- Загрузка и объединение нескольких MP3-файлов.
- Настройка количества файлов в группе для слияния.
- Получение результата в виде ZIP-архива.
- Простой и чистый интерфейс (HTML+Bootstrap).
- Быстрая работа даже на минимальных VPS.

---

## Technologies Used

- Python 3
- Flask
- Werkzeug
- FFmpeg (через системные вызовы)
- Docker (контейнеризация для локального и продакшн деплоя)
- GitHub Actions (CI/CD: тесты, линтеры, автодеплой)
- nginx (reverse-proxy на сервере)
- HTML, CSS (Bootstrap)

---

## Installation

### Prerequisites

- Python 3.x installed.
- FFmpeg installed on your system.
- [Git](https://git-scm.com/) installed.

### Steps
   ```bash
   git clone https://github.com/alfonies666669/mp3-joiner.git
   cd mp3-joiner
   pip install -r requirements.txt
   python app.py
   ```
Перейти на:
   ```
   http://127.0.0.1:5001
   ```

---

## Docker Deployment

### Steps

1. Запуск через Docker:
   ```bash
   docker build -t mp3-joiner .
   ```

2. Запуск Docker контейнера:
   ```bash
   docker run -p 5001:5001 mp3-joiner
   ```

3. Перейти на:
   ```
   http://localhost:5001
   ```

---
## Continuous Integration / Continuous Deployment (CI/CD)
- GitHub Actions автоматизирует:
  - Линтинг и форматирование (black, isort, pylint)
  - Юнит-тесты (pytest)
  - Docker-сборку и healthcheck
  - Автоматический деплой на VPS через SSH
  - Любой коммит в main проходит весь цикл до выкладки на сервер.
---

## Использование

1.	Зайти на главную страницу (/).
2. Загрузить MP3-файлы.
3. Указать число файлов на группу.
4. Нажать “Merge Files”.
5. Скачать архив с результатами.

---

## Roadmap

- Добавить поддержку других аудиоформатов.
- Прогресс-бар и статус для больших файлов.
- Авторизация и личные кабинеты.
- Расширить e2e тесты.
- Интеграция с облачным хранилищем.
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

## Live Demo

В разработке (домен появится после полной публикации).
