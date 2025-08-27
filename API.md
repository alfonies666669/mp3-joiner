# MP3 Joiner — API Reference

Версия API совпадает с версией приложения (см. релизы или шильдик в README).

---

## 1. Базовая информация

|                | Значение |
|----------------|----------|
| **Базовый URL**| `http://127.0.0.1:5001` |
| **Формат ошибок** | JSON `{ "error": "<сообщение>" }` |
| **Content-Type** | `multipart/form-data` для `/merge`, `application/zip` при успехе, JSON — в остальных случаях |

---

## 2. Авторизация и защита

| Действие | Условие |
|----------|---------|
| **Same-Origin + CSRF** | Заголовок `Origin` совпадает с `ALLOWED_ORIGIN` **и** в теле есть `csrf_token`. |
| **Bearer Token** | Заголовок `Authorization: Bearer <TOKEN>`; токены берутся из `TOKEN_FILE_PATH` (если `API_TOKENS_REQUIRED=true`). |

> Для эндпоинтов `/api/test` и `/api/reload-tokens` Bearer-токен обязателен.
> `/api/health` открыт без авторизации.

---

## 3. Лимиты

| Переменная | Назначение | Значение по умолчанию |
|------------|------------|-----------------------|
| `MAX_FILES` | Макс. файлов за запрос | `50` |
| `MAX_PER_FILE_MB` | Макс. размер одного файла (МБ) | `50` |
| `MAX_CONTENT_LENGTH` | Макс. общий размер тела (байт) | `104 857 600` (100 MB) |
| Rate-limit | `RATE_LIMIT_MAX_REQUESTS` / `RATE_LIMIT_WINDOW_SEC` | `20` за `60 c` |

---

## 4. Эндпоинты

### 4.1 `GET /healthz`

| Код | Тело |
|-----|------|
| `200` | ```json\n{\n  "status": "ok",\n  "ffmpeg": true,\n  "max_content_length_mb": 100,\n  "max_files": 50,\n  "max_per_file_mb": 50\n}\n``` |

---

### 4.2 `POST /merge`

| Параметр | Тип | Обязателен |
|----------|-----|------------|
| `files` | множественные `.mp3` | ✔ |
| `count` | целое > 0 | ✔ |
| `csrf_token` | строка | ✔ при Same-Origin |

| Возможные ответы |
|------------------|
| `200` — ZIP `application/zip` c `merged_*.mp3` |
| `400` — валидация / плохой MP3 |
| `401` — нет CSRF или Bearer |
| `403` — неверный Bearer |
| `413` — превышен `MAX_CONTENT_LENGTH` |
| `429` — Rate-limit |
| `500` — внутренняя ошибка |

**Пример**

```bash
curl -X POST http://127.0.0.1:5001/merge \
  -H "Authorization: Bearer $TOKEN" \
  -F "count=3" \
  -F "files=@a.mp3" \
  -F "files=@b.mp3" \
  -F "files=@c.mp3" \
  -o merged_files.zip
```

### 4.3 GET /
HTML-форма загрузки (рендерит csrf_token).

### 4.4 GET /how-it-works
Статическая страница «Как это работает».

### 5. Blueprint /api/*

| Эндпоинт                  | Описание               | Авторизация |
| ------------------------- | ---------------------- | ----------- |
| `GET /api/health`         | состояние токенов/гео  | —           |
| `GET /api/test`           | тест Bearer + (IP/Geo) | Bearer      |
| `POST /api/reload-tokens` | перечитать токены      | Bearer      |

**Примеры**

```bash
# Health
curl http://127.0.0.1:5001/api/health

# Test
curl -H "Authorization: Bearer $TOKEN" \
     http://127.0.0.1:5001/api/test

# Reload tokens
curl -X POST -H "Authorization: Bearer $TOKEN" \
     http://127.0.0.1:5001/api/reload-tokens
```
### 6. Переменные окружения (ключевые)

| env                         | Назначение                    | Пример                           |
| --------------------------- | ----------------------------- | -------------------------------- |
| `SECRET_KEY`                | Flask secret                  | `change-me`                      |
| `ALLOWED_ORIGIN`            | допустимый Origin             | `https://mp3-joiner.ru`          |
| `LOG_DIR` / `USER_LOG_PATH` | каталог логов                 | `/var/logs/mp3_joiner`           |
| `TOKEN_FILE_PATH`           | файл с токенами               | `/app/tokens/allowed_tokens.txt` |
| `API_TOKENS_REQUIRED`       | `true/false`                  | `true`                           |
| `GEO_LOOKUP_ENABLED`        | `true/false`                  | `false`                          |
| …                           | см. `README`/`docker-compose` |                                  |

### 7. Код ответов

| Код | Значение              |
| --- | --------------------- |
| 200 | OK                    |
| 400 | Некорректный запрос   |
| 401 | Нет авторизации       |
| 403 | Запрещено (bad token) |
| 413 | Entity Too Large      |
| 429 | Too Many Requests     |
| 500 | Internal Server Error |

### 8. Примеры curl

```bash
# Здоровье
curl http://127.0.0.1:5001/healthz

# Merge (Bearer)
curl -X POST http://127.0.0.1:5001/merge \
  -H "Authorization: Bearer $TOKEN" \
  -F "count=2" \
  -F "files=@1.mp3" \
  -F "files=@2.mp3" \
  -o merged_files.zip
```
