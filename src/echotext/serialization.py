from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from echotext.models import DeviceIdentity, Peer, TextMessage


def dataclass_to_dict(value: Any) -> dict[str, Any]:
    """Convert a dataclass instance to a plain dictionary."""

    if not is_dataclass(value):
        raise TypeError(f"Expected dataclass instance, got {type(value)!r}")
    return asdict(value)


def identity_from_dict(data: dict[str, Any]) -> DeviceIdentity:
    """Parse and validate a device identity payload."""

    return DeviceIdentity(
        device_id=str(data["device_id"]),
        name=str(data["name"]),
        platform=str(data["platform"]),
        host=str(data["host"]),
        port=int(data["port"]),
    )


def peer_from_dict(data: dict[str, Any]) -> Peer:
    """Parse a peer from persisted or discovered data."""

    return Peer(
        device_id=str(data["device_id"]),
        name=str(data["name"]),
        platform=str(data["platform"]),
        host=str(data["host"]),
        port=int(data["port"]),
        last_seen=float(data.get("last_seen", 0.0)),
        shared_secret=data.get("shared_secret"),
    )


def message_from_dict(data: dict[str, Any]) -> TextMessage:
    """Parse a text message payload."""

    return TextMessage(
        message_id=str(data["message_id"]),
        sender_id=str(data["sender_id"]),
        sender_name=str(data["sender_name"]),
        text=str(data["text"]),
        created_at=float(data["created_at"]),
    )
