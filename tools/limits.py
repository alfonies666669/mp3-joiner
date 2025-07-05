import time
from collections import defaultdict

from flask import request


class RateLimiter:
    def __init__(self, window_sec: int, max_req: int):
        self.window = window_sec
        self.max_req = max_req
        self.bucket = defaultdict(list)

    @staticmethod
    def _key() -> str:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return "t:" + auth.split(" ", 1)[1][:64]
        return "ip:" + (request.remote_addr or "unknown")

    def check(self) -> bool:
        now = time.monotonic()
        key = self._key()
        q = self.bucket[key]
        while q and now - q[0] > self.window:
            q.pop(0)
        if len(q) >= self.max_req:
            return False
        q.append(now)
        return True
