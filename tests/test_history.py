from __future__ import annotations

from echotext.history import HistoryStore
from echotext.models import HistoryEntry


def test_history_deduplicates_messages(tmp_path) -> None:
    history = HistoryStore(tmp_path, persistent=True)
    entry = HistoryEntry("sent", "Laptop", "hello", 1.0, "same-id")

    history.add(entry)
    history.add(entry)

    assert len(history.entries) == 1
    assert history.path.exists()


def test_disable_persistent_history_removes_file(tmp_path) -> None:
    history = HistoryStore(tmp_path, persistent=True)
    history.add(HistoryEntry("received", "Phone", "secret", 1.0, "id"))

    history.set_persistent(False)

    assert history.entries
    assert not history.path.exists()
