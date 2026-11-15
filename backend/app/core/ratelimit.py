"""Brute-force protection for the login endpoint (OWASP API4:2023).

After `login_max_failures` failed attempts for the same user name from the same client IP
within `login_window_seconds`, further attempts get HTTP 429 until the window passes.
A successful login clears the counter.

The state lives in memory, which fits the single-process deployment of this project.
With several workers or instances it would move to a shared store (e.g. Redis).
"""

import threading
import time
from collections import defaultdict, deque


class LoginLimiter:
    def __init__(self, max_failures: int, window_seconds: int) -> None:
        self.max_failures = max_failures
        self.window = window_seconds
        self._failures: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: tuple[str, str], now: float) -> deque[float]:
        attempts = self._failures[key]
        while attempts and now - attempts[0] > self.window:
            attempts.popleft()
        return attempts

    def retry_after(self, ip: str, username: str) -> int | None:
        """Seconds until a new attempt is allowed, or None if it is allowed now."""
        key, now = (ip, username.lower()), time.monotonic()
        with self._lock:
            attempts = self._prune(key, now)
            if len(attempts) < self.max_failures:
                return None
            return max(1, int(self.window - (now - attempts[0])) + 1)

    def failed(self, ip: str, username: str) -> None:
        key, now = (ip, username.lower()), time.monotonic()
        with self._lock:
            self._prune(key, now).append(now)

    def succeeded(self, ip: str, username: str) -> None:
        with self._lock:
            self._failures.pop((ip, username.lower()), None)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()
