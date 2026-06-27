from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceIdentity:
    """Public device identity shared over LAN discovery."""

    device_id: str
    name: str
    platform: str
    host: str
    port: int
    hosts: tuple[str, ...] = ()


@dataclass(frozen=True)
class Peer(DeviceIdentity):
    """A discovered or paired LAN peer."""

    last_seen: float = 0.0
    shared_secret: str | None = None


@dataclass(frozen=True)
class TextMessage:
    """Text payload exchanged between paired devices."""

    message_id: str
    sender_id: str
    sender_name: str
    text: str
    created_at: float


@dataclass(frozen=True)
class HistoryEntry:
    """A sent or received message shown in the UI."""

    direction: str
    peer_name: str
    text: str
    created_at: float
    message_id: str


@dataclass(frozen=True)
class EnvironmentDiagnosis:
    """Summarize desktop environment readiness for LAN operation."""

    lan_ip_ok: bool
    font_ok: bool
    firewall_rule_found: bool
    firewall_scope: str
    warning_key: str
    warning_detail: str
