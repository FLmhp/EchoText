from __future__ import annotations

from echotext.crypto import PairCode, generate_shared_secret
from echotext.models import DeviceIdentity, Peer, TextMessage
from echotext.transport import TransportClient, TransportServer


def test_pair_and_send_message() -> None:
    receiver_identity = DeviceIdentity("receiver", "Receiver", "Windows", "127.0.0.1", 0)
    sender_identity = DeviceIdentity("sender", "Sender", "Windows", "127.0.0.1", 9999)
    pair_code = PairCode()
    paired_peers: dict[str, Peer] = {}
    received: list[TextMessage] = []

    def identity_provider() -> DeviceIdentity:
        return DeviceIdentity(
            receiver_identity.device_id,
            receiver_identity.name,
            receiver_identity.platform,
            "127.0.0.1",
            server.port,
        )

    def peer_provider(device_id: str) -> Peer | None:
        return paired_peers.get(device_id)

    def on_peer_paired(peer: Peer) -> None:
        paired_peers[peer.device_id] = peer

    def on_message(message: TextMessage, _peer: Peer) -> None:
        received.append(message)

    server = TransportServer(identity_provider, pair_code.matches, peer_provider, on_message, on_peer_paired)
    server.start()
    try:
        client = TransportClient()
        target = Peer("receiver", "Receiver", "Windows", "127.0.0.1", server.port)
        secret = generate_shared_secret()
        client.pair(target, sender_identity, pair_code.code, secret)
        paired_target = Peer("receiver", "Receiver", "Windows", "127.0.0.1", server.port, shared_secret=secret)
        message = TextMessage("message-id", "sender", "Sender", "hello", 1.0)

        client.send_message(paired_target, message)

        assert paired_peers["sender"].shared_secret == secret
        assert received == [message]
    finally:
        server.stop()
