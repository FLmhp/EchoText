from __future__ import annotations

import socket

import pytest

from echotext.crypto import PairCode, generate_shared_secret
from echotext.models import DeviceIdentity, Peer, TextMessage
from echotext.transport import DEFAULT_TRANSPORT_PORT, TransportClient, TransportServer


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

    server = TransportServer(
        identity_provider, pair_code.matches, peer_provider, on_message, on_peer_paired, preferred_port=0
    )
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


def test_transport_server_prefers_stable_port() -> None:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        probe.bind(("", DEFAULT_TRANSPORT_PORT))
    except OSError:
        pytest.skip("stable transport port is already in use on this machine")
    finally:
        probe.close()
    identity = DeviceIdentity("receiver", "Receiver", "Windows", "127.0.0.1", 0)
    server = TransportServer(
        lambda: identity, lambda code: True, lambda device_id: None, lambda message, peer: None, lambda peer: None
    )
    try:
        server.start()
        assert server.port == DEFAULT_TRANSPORT_PORT
    finally:
        server.stop()


def test_transport_server_falls_back_when_stable_port_is_taken() -> None:
    occupied_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        occupied_socket.bind(("", DEFAULT_TRANSPORT_PORT))
    except OSError:
        occupied_socket.close()
        pytest.skip("stable transport port is already in use by another process")
    occupied_socket.listen(1)
    identity = DeviceIdentity("receiver", "Receiver", "Windows", "127.0.0.1", 0)
    server = TransportServer(
        lambda: identity, lambda code: True, lambda device_id: None, lambda message, peer: None, lambda peer: None
    )
    try:
        server.start()
        assert server.port not in {0, DEFAULT_TRANSPORT_PORT}
    finally:
        server.stop()
        occupied_socket.close()
