from __future__ import annotations

import time
import uuid
from collections.abc import Callable

from echotext.crypto import PairCode, generate_shared_secret
from echotext.discovery import DiscoveryService
from echotext.history import HistoryStore
from echotext.models import DeviceIdentity, HistoryEntry, Peer, TextMessage
from echotext.network import local_lan_ip
from echotext.settings import SettingsStore
from echotext.transport import TransportClient, TransportError, TransportServer


class EchoTextRuntime:
    """Coordinates discovery, pairing, messaging, settings, and history."""

    def __init__(
        self,
        settings: SettingsStore | None = None,
        on_message: Callable[[HistoryEntry], None] | None = None,
        on_peer_paired: Callable[[Peer], None] | None = None,
    ) -> None:
        self.settings = settings or SettingsStore()
        self.pair_code = PairCode()
        self._host = local_lan_ip()
        self._identity = self.settings.identity(self._host, 0)
        self._paired_peers = self.settings.peers()
        self._discovered_peers: dict[str, Peer] = {}
        self.history = HistoryStore(self.settings.data_dir, self.settings.persistent_history_enabled())
        self.client = TransportClient()
        self._on_message = on_message
        self._on_peer_paired = on_peer_paired
        self.server = TransportServer(
            self.identity,
            self.pair_code.matches,
            self.peer,
            self._handle_message,
            self._handle_peer_paired,
        )
        self.discovery = DiscoveryService(self.identity)

    def start(self) -> None:
        """Start network services."""

        self.server.start()
        self._identity = self.settings.identity(self._host, self.server.port)
        self.discovery.start()

    def stop(self) -> None:
        """Stop network services."""

        self.discovery.stop()
        self.server.stop()

    def identity(self) -> DeviceIdentity:
        """Return the current local identity."""

        return self._identity

    def peer(self, device_id: str) -> Peer | None:
        """Return a paired peer by device ID."""

        return self._paired_peers.get(device_id)

    def peers(self) -> list[Peer]:
        """Return merged discovered and paired peers."""

        for discovered in self.discovery.peers():
            existing = self._paired_peers.get(discovered.device_id)
            if existing is None:
                self._discovered_peers[discovered.device_id] = discovered
            else:
                self._paired_peers[discovered.device_id] = Peer(
                    device_id=existing.device_id,
                    name=existing.name,
                    platform=existing.platform,
                    host=discovered.host,
                    port=discovered.port,
                    last_seen=discovered.last_seen,
                    shared_secret=existing.shared_secret,
                )
        peers = {**self._discovered_peers, **self._paired_peers}
        return sorted(peers.values(), key=lambda peer: peer.name.lower())

    def pair_with_peer(self, peer: Peer, pair_code: str) -> Peer:
        """Pair with a peer using its visible code."""

        shared_secret = generate_shared_secret()
        peer_identity = self.client.pair(peer, self.identity(), pair_code, shared_secret)
        paired = Peer(
            device_id=peer_identity.device_id,
            name=peer_identity.name,
            platform=peer_identity.platform,
            host=peer_identity.host,
            port=peer_identity.port,
            last_seen=time.time(),
            shared_secret=shared_secret,
        )
        self._save_peer(paired)
        return paired

    def send_text(self, peer: Peer, text: str) -> HistoryEntry:
        """Send text to a paired peer."""

        paired = self._paired_peers.get(peer.device_id)
        if paired is None:
            raise TransportError("Pair with the device before sending text")
        message = TextMessage(
            message_id=uuid.uuid4().hex,
            sender_id=self.identity().device_id,
            sender_name=self.identity().name,
            text=text,
            created_at=time.time(),
        )
        self.client.send_message(paired, message)
        entry = HistoryEntry("sent", paired.name, text, message.created_at, message.message_id)
        self.history.add(entry)
        return entry

    def set_persistent_history(self, enabled: bool) -> None:
        """Persist the history preference."""

        self.settings.set_persistent_history_enabled(enabled)
        self.history.set_persistent(enabled)

    def clear_history(self) -> None:
        """Clear local message history."""

        self.history.clear()

    def _handle_message(self, message: TextMessage, peer: Peer) -> None:
        entry = HistoryEntry("received", peer.name, message.text, message.created_at, message.message_id)
        self.history.add(entry)
        if self._on_message is not None:
            self._on_message(entry)

    def _handle_peer_paired(self, peer: Peer) -> None:
        self._save_peer(peer)
        if self._on_peer_paired is not None:
            self._on_peer_paired(peer)

    def _save_peer(self, peer: Peer) -> None:
        self._paired_peers[peer.device_id] = peer
        self.settings.save_peer(peer)
