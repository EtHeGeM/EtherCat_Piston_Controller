from __future__ import annotations

import threading
from collections import deque
from datetime import datetime
from typing import List


class LogBuffer:
    """Thread-safe bounded log buffer."""

    def __init__(self, max_entries: int = 300) -> None:
        self.max_entries = max_entries
        self._items: deque[str] = deque(maxlen=max_entries)
        self._lock = threading.Lock()

    def add(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {message}"
        with self._lock:
            self._items.append(entry)

    def get_lines(self, limit: int | None = None) -> List[str]:
        with self._lock:
            if limit is None or limit >= len(self._items):
                return list(self._items)
            return list(self._items)[-limit:]

    def as_text(self, limit: int | None = None) -> str:
        return "\n".join(self.get_lines(limit=limit))
