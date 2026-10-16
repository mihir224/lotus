from collections import defaultdict, deque
from threading import Lock
from time import monotonic


class FixedWindowRateLimiter:
    """Small per-instance limiter for authenticated agent requests."""

    def __init__(self, requests: int, window_seconds: int):
        self.requests = requests
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> int | None:
        now = monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.requests:
                return max(1, int(events[0] + self.window_seconds - now) + 1)
            events.append(now)
        return None
