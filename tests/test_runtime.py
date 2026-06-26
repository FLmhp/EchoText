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
