from __future__ import annotations

import json
import platform
import socket
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from echotext.models import DeviceIdentity, Peer
from echotext.serialization import peer_from_dict


def default_data_dir() -> Path:
    """Return a cross-platform application data directory."""

    if _is_android():
        try:
            from android.storage import app_storage_path

            return Path(app_storage_path()) / "EchoText"
        except Exception:
            pass

    home = Path.home()
    if platform.system().lower() == "windows":
        return Path.home() / "AppData" / "Roaming" / "EchoText"
    return home / ".echotext"


def _is_android() -> bool:
    """Return whether the current runtime is Android."""

    try:
        from kivy.utils import platform as kivy_platform

        return kivy_platform == "android"
    except Exception:
        return False


class SettingsStore:
    """JSON-backed settings store."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or default_data_dir()
        self.path = self.data_dir / "settings.json"
        self.data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load settings from disk."""

        if not self.path.exists():
            self.data = {}
            return
        self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def save(self) -> None:
        """Persist settings to disk."""

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    def identity(self, host: str, port: int) -> DeviceIdentity:
        """Return the local identity, creating stable values on first run."""

        if "device_id" not in self.data:
            self.data["device_id"] = uuid.uuid4().hex
        if "device_name" not in self.data:
            self.data["device_name"] = socket.gethostname() or "EchoText"
        self.save()
        return DeviceIdentity(
            device_id=str(self.data["device_id"]),
            name=str(self.data["device_name"]),
            platform=platform.system() or "Unknown",
            host=host,
            port=port,
        )

    def peers(self) -> dict[str, Peer]:
        """Return paired peers keyed by device ID."""

        raw_peers = self.data.get("peers", {})
        return {device_id: peer_from_dict(peer) for device_id, peer in raw_peers.items()}

    def save_peer(self, peer: Peer) -> None:
        """Persist a paired peer."""

        peers = self.data.setdefault("peers", {})
        peers[peer.device_id] = asdict(peer)
        self.save()

    def persistent_history_enabled(self) -> bool:
        """Return whether message history should survive restarts."""

        return bool(self.data.get("persistent_history", False))

    def set_persistent_history_enabled(self, enabled: bool) -> None:
        """Persist the message history setting."""

        self.data["persistent_history"] = enabled
        self.save()

    def language(self) -> str:
        """Return the UI language preference."""

        return str(self.data.get("language", "auto"))

    def set_language(self, language: str) -> None:
        """Persist the UI language preference."""

        self.data["language"] = language
        self.save()
