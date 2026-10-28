# -*- coding: utf-8 -*-
import time
import threading


class Throttle:
    """Counts failures per key inside a sliding window (per worker process)."""

    def __init__(self, limit, window_seconds):
        self.limit = limit
        self.window = window_seconds
        self._hits = {}
        self._lock = threading.Lock()

    def _recent(self, key, now):
        hits = [t for t in self._hits.get(key, []) if now - t < self.window]
        if hits:
            self._hits[key] = hits
        else:
            self._hits.pop(key, None)
        return hits

    def blocked(self, key):
        with self._lock:
            return len(self._recent(key, time.time())) >= self.limit

    def hit(self, key):
        with self._lock:
            now = time.time()
            hits = self._recent(key, now)
            hits.append(now)
            self._hits[key] = hits

    def reset(self, key):
        with self._lock:
            self._hits.pop(key, None)
