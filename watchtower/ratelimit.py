from __future__ import annotations

from collections import deque
from threading import Lock
from time import monotonic


class SlidingWindowLimiter:
    """Bounds how often the published demo key may change state.

    The demo key is printed in the README so judges can drive the full
    decision loop themselves. Nothing it reaches can act on the outside world,
    but each incident does invoke four Gemini stages, so the rate is capped to
    keep a public credential from turning into an unbounded model bill.

    Cloud Run runs this service at a maximum of one instance, so in-process
    counters are an accurate global view.
    """

    def __init__(self, limit: int, window_seconds: float):
        if limit < 1:
            raise ValueError("Rate limit must allow at least one request.")
        if window_seconds <= 0:
            raise ValueError("Rate limit window must be positive.")
        self.limit = limit
        self.window_seconds = float(window_seconds)
        self._hits: deque[float] = deque()
        self._lock = Lock()

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._hits and self._hits[0] <= cutoff:
            self._hits.popleft()

    def try_acquire(self, now: float | None = None) -> bool:
        now = monotonic() if now is None else now
        with self._lock:
            self._prune(now)
            if len(self._hits) >= self.limit:
                return False
            self._hits.append(now)
            return True

    def retry_after_seconds(self, now: float | None = None) -> int:
        """Whole seconds until the oldest hit leaves the window."""
        now = monotonic() if now is None else now
        with self._lock:
            self._prune(now)
            if not self._hits or len(self._hits) < self.limit:
                return 0
            return max(1, int(self._hits[0] + self.window_seconds - now) + 1)

    def remaining(self, now: float | None = None) -> int:
        now = monotonic() if now is None else now
        with self._lock:
            self._prune(now)
            return max(0, self.limit - len(self._hits))
