from __future__ import annotations

import json
from pathlib import Path

from echotext.models import Peer, TextMessage
from echotext.runtime import EchoTextRuntime
from echotext.settings import SettingsStore


class _FakeClient:
    def __init__(self) -> None:
        self.peer: Peer | None = None

    def send_message(self, peer: Peer, _message: object) -> str:
        self.peer = peer
        return peer.host


def test_send_text_uses_selected_peer_connection_with_paired_secret(tmp_path: Path) -> None:
    settings = SettingsStore(tmp_path)
    runtime = EchoTextRuntime(settings=settings)
    runtime.client = _FakeClient()
    runtime._paired_peers["phone"] = Peer(
        device_id="phone",
        name="Phone",
        platform="Android",
        host="198.18.0.1",
        port=9000,
        last_seen=1.0,
        shared_secret="secret",
    )
    selected_peer = Peer(
        device_id="phone",
        name="Phone",
        platform="Android",
        host="192.168.3.7",
        port=48735,
        last_seen=2.0,
    )

    runtime.send_text(selected_peer, "hello")

    assert runtime.client.peer is not None
    assert runtime.client.peer.host == "192.168.3.7"
    assert runtime.client.peer.port == 48735
    assert runtime.client.peer.shared_secret == "secret"
    assert runtime.client.peer.hosts == ("192.168.3.7", "198.18.0.1")


def test_peers_prefer_latest_seen_device_for_same_name_and_platform(tmp_path: Path) -> None:
    settings = SettingsStore(tmp_path)
    runtime = EchoTextRuntime(settings=settings)
    runtime._paired_peers["old-phone"] = Peer(
        device_id="old-phone",
        name="Phone",
        platform="Android",
        host="192.168.3.7",
        port=48735,
        last_seen=1.0,
        shared_secret="secret",
    )
    runtime._discovered_peers["new-phone"] = Peer(
        device_id="new-phone",
        name="Phone",
        platform="Android",
        host="192.168.3.8",
        port=48735,
        last_seen=2.0,
    )

    peers = runtime.peers()

    assert len(peers) == 1
    assert peers[0].device_id == "new-phone"


def test_save_peer_prunes_stale_duplicate_identity(tmp_path: Path) -> None:
    settings = SettingsStore(tmp_path)
    settings.save_peer(
        Peer(
            device_id="old-phone",
            name="Phone",
            platform="Android",
            host="192.168.3.7",
            port=48735,
            last_seen=1.0,
            shared_secret="old-secret",
        )
    )

    settings.save_peer(
        Peer(
            device_id="new-phone",
            name="Phone",
            platform="Android",
            host="192.168.3.8",
            port=48735,
            last_seen=2.0,
            shared_secret="new-secret",
        )
    )

    peers = settings.peers()

    assert list(peers) == ["new-phone"]
    assert peers["new-phone"].shared_secret == "new-secret"


def test_runtime_persists_auto_sync_preference(tmp_path: Path) -> None:
    runtime = EchoTextRuntime(settings=SettingsStore(tmp_path))

    assert runtime.auto_sync_enabled() is False

    runtime.set_auto_sync_enabled(True)

    assert runtime.auto_sync_enabled() is True


def test_incoming_message_refreshes_saved_peer_address(tmp_path: Path) -> None:
    runtime = EchoTextRuntime(settings=SettingsStore(tmp_path))
    runtime._paired_peers["pc"] = Peer(
        device_id="pc",
        name="PC",
        platform="Windows",
        host="2403:ac00:b101:1904:59fa:30d5:5be5:f737",
        port=48735,
        hosts=("2403:ac00:b101:1904:59fa:30d5:5be5:f737",),
        last_seen=1.0,
        shared_secret="secret",
    )

    runtime._handle_message(
        TextMessage("message-id", "pc", "PC", "hello", 2.0),
        Peer(
            device_id="pc",
            name="PC",
            platform="Windows",
            host="2403:ac00:b101:1904:c6a4:9ef7:84f9:40d8",
            port=48735,
            hosts=(
                "2403:ac00:b101:1904:c6a4:9ef7:84f9:40d8",
                "2403:ac00:b101:1904:59fa:30d5:5be5:f737",
            ),
            last_seen=2.0,
            shared_secret="secret",
        ),
    )

    assert runtime._paired_peers["pc"].host == "2403:ac00:b101:1904:c6a4:9ef7:84f9:40d8"
    assert runtime._paired_peers["pc"].hosts == (
        "2403:ac00:b101:1904:c6a4:9ef7:84f9:40d8",
        "2403:ac00:b101:1904:59fa:30d5:5be5:f737",
    )


def test_discovery_callback_fires_for_new_peer(tmp_path: Path) -> None:
    changes: list[str] = []
    runtime = EchoTextRuntime(settings=SettingsStore(tmp_path), on_peers_changed=lambda: changes.append("changed"))
    identity = runtime.identity()
    payload = {
        "magic": "ECHOTEXT_DISCOVERY_V1",
        "device": {
            "device_id": "phone",
            "name": "Phone",
            "platform": "Android",
            "host": "192.168.3.7",
            "port": 48735,
        },
    }

    runtime.discovery._handle_packet(json.dumps(payload).encode("utf-8"), "192.168.3.7")  # noqa: SLF001

    assert identity.device_id != "phone"
    assert changes == ["changed"]


def test_peers_merge_discovered_and_paired_hosts(tmp_path: Path) -> None:
    runtime = EchoTextRuntime(settings=SettingsStore(tmp_path))
    runtime._paired_peers["phone"] = Peer(
        device_id="phone",
        name="Phone",
        platform="Android",
        host="192.168.43.236",
        port=48735,
        hosts=("192.168.43.236",),
        last_seen=1.0,
        shared_secret="secret",
    )
    payload = {
        "magic": "ECHOTEXT_DISCOVERY_V1",
        "device": {
            "device_id": "phone",
            "name": "Phone",
            "platform": "Android",
            "host": "172.21.100.161",
            "hosts": ["172.21.100.161", "10.127.107.72"],
            "port": 48735,
        },
    }

    runtime.discovery._handle_packet(json.dumps(payload).encode("utf-8"), "172.21.100.161")  # noqa: SLF001

    peer = runtime.peers()[0]
    assert peer.host == "172.21.100.161"
    assert peer.hosts == ("172.21.100.161", "10.127.107.72", "192.168.43.236")
