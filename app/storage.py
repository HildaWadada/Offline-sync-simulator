"""Small JSON-file persistence standing in for on-device storage
(e.g. SQLite/IndexedDB on a field tool) and a "server" record store.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class _JsonFile:
    """Atomic read/write of one JSON file. `path=None` means in-memory only."""

    def __init__(self, path: str | None, fallback: Any):
        self.path = Path(path) if path else None
        self.fallback = fallback

    def read(self) -> Any:
        if self.path is None or not self.path.exists():
            return json.loads(json.dumps(self.fallback))  # deep copy
        return json.loads(self.path.read_text(encoding="utf-8"))

    def write(self, data: Any) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, self.path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise


class OfflineQueue:
    """Records are cached here until a sync succeeds. Pass no path for in-memory."""

    def __init__(self, path: str | None = None):
        self._io = _JsonFile(path, [])
        self._items: list[dict] = self._io.read()

    def enqueue(self, records: list[dict] | dict) -> None:
        if isinstance(records, dict):
            records = [records]
        self._items.extend(records)
        self._io.write(self._items)

    def peek(self) -> list[dict]:
        return list(self._items)

    @property
    def size(self) -> int:
        return len(self._items)

    def ack(self, n: int) -> None:
        """Remove the first n items. Only call after a successful commit."""
        del self._items[:n]
        self._io.write(self._items)


class RecordStore:
    """The "server": committed records keyed by submission_uuid, plus a reject log."""

    def __init__(self, path: str | None = None):
        self._io = _JsonFile(path, {"records": [], "rejected": []})
        self._state: dict = self._io.read()

    def has(self, submission_uuid: str) -> bool:
        return any(r["submission_uuid"] == submission_uuid for r in self._state["records"])

    @property
    def records(self) -> list[dict]:
        return list(self._state["records"])

    @property
    def rejected(self) -> list[dict]:
        return list(self._state["rejected"])

    def commit(self, records: list[dict], rejected: list[dict] | None = None) -> None:
        """Single write = all-or-nothing commit for the batch."""
        self._state = {
            "records": [*self._state["records"], *records],
            "rejected": [*self._state["rejected"], *(rejected or [])],
        }
        self._io.write(self._state)
