from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Callable

from echotext.models import DeviceIdentity, Peer
from echotext.serialization import dataclass_to_dict, identity_from_dict

DISCOVERY_PORT = 48734
DISCOVERY_MAGIC = "ECHOTEXT_DISCOVERY_V1"


class DiscoveryService:
    """UDP broadcaster and listener for LAN peers."""

    def __init__(self, identity_provider: Callable[[], DeviceIdentity]) -> None:
        self.identity_provider = identity_provider
        self._peers: dict[str, Peer] = {}
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        """Start background discovery threads."""

        self._threads = [
            threading.Thread(target=self._broadcast_loop, name="echotext-discovery-broadcast", daemon=True),
            threading.Thread(target=self._listen_loop, name="echotext-discovery-listen", daemon=True),
        ]
        for thread in self._threads:
            thread.start()

    def stop(self) -> None:
        """Stop discovery threads."""

        self._stop_event.set()
        for thread in self._threads:
            thread.join(timeout=1)

    def peers(self) -> list[Peer]:
        """Return discovered peers sorted by name."""

        return sorted(self._peers.values(), key=lambda peer: peer.name.lower())

    def _broadcast_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            while not self._stop_event.is_set():
                identity = self.identity_provider()
                payload = {"magic": DISCOVERY_MAGIC, "device": dataclass_to_dict(identity)}
                sock.sendto(json.dumps(payload).encode("utf-8"), ("255.255.255.255", DISCOVERY_PORT))
                self._stop_event.wait(2)
        finally:
            sock.close()

    def _listen_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", DISCOVERY_PORT))
        sock.settimeout(1)
        try:
            while not self._stop_event.is_set():
                try:
                    data, address = sock.recvfrom(8192)
                except TimeoutError:
                    continue
                except OSError:
                    continue
                self._handle_packet(data, address[0])
        finally:
            sock.close()

    def _handle_packet(self, data: bytes, source_host: str) -> None:
        try:
            payload = json.loads(data.decode("utf-8"))
            if payload.get("magic") != DISCOVERY_MAGIC:
                return
            identity = identity_from_dict(payload["device"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return

        local_identity = self.identity_provider()
        if identity.device_id == local_identity.device_id:
            return

        host = identity.host if identity.host != "127.0.0.1" else source_host
        self._peers[identity.device_id] = Peer(
            device_id=identity.device_id,
            name=identity.name,
            platform=identity.platform,
            host=host,
            port=identity.port,
            last_seen=time.time(),
        )
