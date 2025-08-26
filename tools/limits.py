"""
Simple in-memory rate limiter.

Notes:
- Not multi-process safe (gunicorn workers будут иметь отдельные бакеты).
- Не защищает от перезапуска процесса.
"""

import time
from collections import deque, defaultdict

from flask import request


class RateLimiter:
    """Fixed-window rate limiter, keyed by bearer token (если есть) или IP."""

    def __init__(self, window_sec: int, max_req: int) -> None:
        """
        :param window_sec: Длина окна (секунды).
        :param max_req: Максимум запросов на ключ за окно.
        """
        self.window = window_sec
        self.max_req = max_req
        # ключ -> очередь меток времени
        self.bucket: dict[str, deque[float]] = defaultdict(deque)

    @staticmethod
    def _key() -> str:
        """
        Построить ключ для лимита: токен (если Bearer есть) или IP.
        """
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return "t:" + auth.split(" ", 1)[1][:64]
        return "ip:" + (request.remote_addr or "unknown")

    def check(self) -> bool:
        """
        Проверить и записать текущий запрос.
        Возвращает True, если лимит НЕ превышен.
        """
        now = time.monotonic()
        key = self._key()
        q = self.bucket[key]

        # выкидываем старые элементы за пределами окна
        limit_from = now - self.window
        while q and q[0] <= limit_from:
            q.popleft()

        if len(q) >= self.max_req:
            return False

        q.append(now)
        return True
