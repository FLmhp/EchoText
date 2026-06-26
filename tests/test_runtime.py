from __future__ import annotations

from pathlib import Path

from echotext.models import Peer
from echotext.runtime import EchoTextRuntime
from echotext.settings import SettingsStore


class _FakeClient:
    def __init__(self) -> None:
        self.peer: Peer | None = None

    def send_message(self, peer: Peer, _message: object) -> None:
        self.peer = peer


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
