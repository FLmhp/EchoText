from __future__ import annotations

import time
import uuid
from collections.abc import Callable

from echotext.crypto import PairCode, generate_shared_secret
from echotext.discovery import DiscoveryService
from echotext.history import HistoryStore
from echotext.models import DeviceIdentity, HistoryEntry, Peer, TextMessage
from echotext.network import lan_ipv4_candidates, lan_ipv6_candidates, normalize_hosts, parse_host_endpoint
from echotext.settings import SettingsStore
from echotext.transport import DEFAULT_TRANSPORT_PORT, TransportClient, TransportError, TransportServer


class EchoTextRuntime:
    """Coordinates discovery, pairing, messaging, settings, and history."""

    def __init__(
        self,
        settings: SettingsStore | None = None,
        on_message: Callable[[HistoryEntry], None] | None = None,
        on_peer_paired: Callable[[Peer], None] | None = None,
        on_peers_changed: Callable[[], None] | None = None,
    ) -> None:
        self.settings = settings or SettingsStore()
        self.pair_code = PairCode()
        self._hosts = tuple(lan_ipv4_candidates())
        self._host = self._hosts[0] if self._hosts else "127.0.0.1"
        self._identity = self.settings.identity(self._host, 0, self._hosts)
        self._paired_peers = self.settings.peers()
        self._discovered_peers: dict[str, Peer] = {}
        self.history = HistoryStore(self.settings.data_dir, self.settings.persistent_history_enabled())
        self.client = TransportClient()
        self._on_message = on_message
        self._on_peer_paired = on_peer_paired
        self._on_peers_changed = on_peers_changed
        self.server = TransportServer(
            self.identity,
            self.pair_code.matches,
            self.peer,
            self._handle_message,
            self._handle_peer_paired,
        )
        self.discovery = DiscoveryService(self.identity, self._handle_peers_changed)

    def start(self) -> None:
        """Start network services."""

        self.server.start()
        self._refresh_identity(self.server.port)
        self.discovery.start()

    def stop(self) -> None:
        """Stop network services."""

        self.discovery.stop()
        self.server.stop()

    def identity(self) -> DeviceIdentity:
        """Return the current local identity."""

        self._refresh_identity(self.server.port)
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
                hosts = normalize_hosts(discovered.host, [*discovered.hosts, existing.host, *existing.hosts])
                self._paired_peers[discovered.device_id] = Peer(
                    device_id=existing.device_id,
                    name=existing.name,
                    platform=existing.platform,
                    host=hosts[0],
                    port=discovered.port,
                    hosts=hosts,
                    last_seen=discovered.last_seen,
                    shared_secret=existing.shared_secret,
                )
        peers = {**self._discovered_peers, **self._paired_peers}
        return _dedupe_peers(sorted(peers.values(), key=lambda peer: peer.name.lower()))

    def pair_with_peer(self, peer: Peer, pair_code: str) -> Peer:
        """Pair with a peer using its visible code."""

        shared_secret = generate_shared_secret()
        peer_identity, connected_host = self.client.pair(peer, self.identity(), pair_code, shared_secret)
        if peer.device_id and peer_identity.device_id != peer.device_id:
            raise TransportError("Reached another device at a stale address. Refresh the device list and try again.")
        hosts = normalize_hosts(connected_host, [*peer.hosts, peer_identity.host, *peer_identity.hosts])
        paired = Peer(
            device_id=peer_identity.device_id,
            name=peer_identity.name,
            platform=peer_identity.platform,
            host=hosts[0],
            port=peer_identity.port,
            hosts=hosts,
            last_seen=time.time(),
            shared_secret=shared_secret,
        )
        self._save_peer(paired)
        return paired

    def send_text(self, peer: Peer, text: str) -> HistoryEntry:
        """Send text to a paired peer."""

        paired = self._paired_peers.get(peer.device_id)
        if paired is None or paired.shared_secret is None:
            raise TransportError("Pair with the device before sending text")
        active_peer = Peer(
            device_id=paired.device_id,
            name=paired.name,
            platform=paired.platform,
            host=peer.host,
            port=peer.port,
            hosts=normalize_hosts(peer.host, [*peer.hosts, paired.host, *paired.hosts]),
            last_seen=peer.last_seen,
            shared_secret=paired.shared_secret,
        )
        message = TextMessage(
            message_id=uuid.uuid4().hex,
            sender_id=self.identity().device_id,
            sender_name=self.identity().name,
            text=text,
            created_at=time.time(),
        )
        connected_host = self.client.send_message(active_peer, message)
        updated_hosts = normalize_hosts(connected_host, [*active_peer.hosts, paired.host, *paired.hosts])
        self._save_peer(
            Peer(
                device_id=paired.device_id,
                name=paired.name,
                platform=paired.platform,
                host=updated_hosts[0],
                port=active_peer.port,
                hosts=updated_hosts,
                last_seen=time.time(),
                shared_secret=paired.shared_secret,
            )
        )
        entry = HistoryEntry("sent", active_peer.name, text, message.created_at, message.message_id)
        self.history.add(entry)
        return entry

    def set_persistent_history(self, enabled: bool) -> None:
        """Persist the history preference."""

        self.settings.set_persistent_history_enabled(enabled)
        self.history.set_persistent(enabled)

    def clear_history(self) -> None:
        """Clear local message history."""

        self.history.clear()

    def refresh_discovery(self) -> None:
        """Trigger an active discovery probe."""

        self._refresh_identity(self.server.port)
        self.discovery.probe()

    def resolve_peer(self, endpoint_text: str) -> Peer:
        """Resolve a direct-connect endpoint into a selectable peer."""

        endpoint = parse_host_endpoint(endpoint_text, default_port=DEFAULT_TRANSPORT_PORT)
        peer_identity = self.client.hello(endpoint.host, endpoint.port)
        existing = self._paired_peers.get(peer_identity.device_id)
        hosts = normalize_hosts(
            endpoint.host,
            [
                *peer_identity.hosts,
                peer_identity.host,
                *(existing.hosts if existing is not None else ()),
            ],
        )
        resolved = Peer(
            device_id=peer_identity.device_id,
            name=peer_identity.name,
            platform=peer_identity.platform,
            host=hosts[0],
            port=peer_identity.port,
            hosts=hosts,
            last_seen=time.time(),
            shared_secret=existing.shared_secret if existing is not None else None,
        )
        if existing is None:
            self._discovered_peers[resolved.device_id] = resolved
        else:
            self._paired_peers[resolved.device_id] = resolved
        if self._on_peers_changed is not None:
            self._on_peers_changed()
        return resolved

    def local_ipv6_address(self) -> str | None:
        """Return the preferred local IPv6 address for manual sharing."""

        candidates = lan_ipv6_candidates()
        return candidates[0] if candidates else None

    def set_auto_sync_enabled(self, enabled: bool) -> None:
        """Persist the foreground auto sync setting."""

        self.settings.set_auto_sync_enabled(enabled)

    def auto_sync_enabled(self) -> bool:
        """Return the foreground auto sync setting."""

        return self.settings.auto_sync_enabled()

    def _handle_message(self, message: TextMessage, peer: Peer) -> None:
        self._save_peer(peer)
        entry = HistoryEntry("received", peer.name, message.text, message.created_at, message.message_id)
        self.history.add(entry)
        if self._on_message is not None:
            self._on_message(entry)

    def _handle_peer_paired(self, peer: Peer) -> None:
        self._save_peer(peer)
        if self._on_peer_paired is not None:
            self._on_peer_paired(peer)

    def _handle_peers_changed(self) -> None:
        if self._on_peers_changed is not None:
            self._on_peers_changed()

    def _save_peer(self, peer: Peer) -> None:
        self._paired_peers[peer.device_id] = peer
        self.settings.save_peer(peer)

    def _refresh_identity(self, port: int) -> None:
        hosts = tuple(lan_ipv4_candidates())
        host = hosts[0] if hosts else "127.0.0.1"
        if host == self._host and hosts == self._hosts and self._identity.port == port:
            return
        self._host = host
        self._hosts = hosts
        self._identity = self.settings.identity(host, port, hosts)


def _dedupe_peers(peers: list[Peer]) -> list[Peer]:
    chosen: dict[tuple[str, str], Peer] = {}
    for peer in peers:
        key = (peer.name.casefold(), peer.platform.casefold())
        existing = chosen.get(key)
        if existing is None or _peer_rank(peer) > _peer_rank(existing):
            chosen[key] = peer
    return sorted(chosen.values(), key=lambda peer: peer.name.lower())


def _peer_rank(peer: Peer) -> tuple[float, int]:
    return (peer.last_seen, 1 if peer.shared_secret else 0)
