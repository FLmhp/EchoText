from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from echotext.models import HistoryEntry


class HistoryStore:
    """Session and optional persistent history storage."""

    def __init__(self, data_dir: Path, persistent: bool = False, limit: int = 100) -> None:
        self.data_dir = data_dir
        self.path = self.data_dir / "history.json"
        self.persistent = persistent
        self.limit = limit
        self.entries: list[HistoryEntry] = []
        if self.persistent:
            self.load()

    def set_persistent(self, persistent: bool) -> None:
        """Enable or disable persistent history."""

        self.persistent = persistent
        if persistent:
            self.save()
        elif self.path.exists():
            self.path.unlink()

    def load(self) -> None:
        """Load persistent history from disk."""

        if not self.path.exists():
            return
        raw_entries = json.loads(self.path.read_text(encoding="utf-8"))
        self.entries = [
            HistoryEntry(
                direction=str(entry["direction"]),
                peer_name=str(entry["peer_name"]),
                text=str(entry["text"]),
                created_at=float(entry["created_at"]),
                message_id=str(entry["message_id"]),
            )
            for entry in raw_entries[-self.limit :]
        ]

    def add(self, entry: HistoryEntry) -> None:
        """Append an entry and persist if configured."""

        if any(existing.message_id == entry.message_id for existing in self.entries):
            return
        self.entries.append(entry)
        self.entries = self.entries[-self.limit :]
        if self.persistent:
            self.save()

    def clear(self) -> None:
        """Clear all history."""

        self.entries.clear()
        if self.path.exists():
            self.path.unlink()

    def save(self) -> None:
        """Persist history to disk."""

        self.data_dir.mkdir(parents=True, exist_ok=True)
        payload = [asdict(entry) for entry in self.entries[-self.limit :]]
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
