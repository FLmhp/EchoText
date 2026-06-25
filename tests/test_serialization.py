from __future__ import annotations

from echotext.models import DeviceIdentity, Peer, TextMessage
from echotext.serialization import dataclass_to_dict, identity_from_dict, message_from_dict, peer_from_dict


def test_identity_round_trip() -> None:
    identity = DeviceIdentity("id", "Phone", "Android", "192.168.1.2", 1234)

    parsed = identity_from_dict(dataclass_to_dict(identity))

    assert parsed == identity


def test_peer_round_trip() -> None:
    peer = Peer("id", "Desktop", "Windows", "192.168.1.3", 4321, 10.0, "secret")

    parsed = peer_from_dict(dataclass_to_dict(peer))

    assert parsed == peer


def test_message_round_trip() -> None:
    message = TextMessage("mid", "sender", "Phone", "hello", 5.0)

    parsed = message_from_dict(dataclass_to_dict(message))

    assert parsed == message
