from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from echotext.models import DeviceIdentity, Peer
from echotext.network import broadcast_targets, normalize_hosts, should_prefer_source_host, subnet_scan_targets
from echotext.serialization import dataclass_to_dict, identity_from_dict
from echotext.transport import DEFAULT_TRANSPORT_PORT, TransportClient, TransportError

DISCOVERY_PORT = 48734
DISCOVERY_MAGIC = "ECHOTEXT_DISCOVERY_V1"
DISCOVERY_REQUEST_MAGIC = "ECHOTEXT_DISCOVERY_REQ_V1"


class DiscoveryService:
    """UDP broadcaster and listener for LAN peers."""

    def __init__(
        self,
        identity_provider: Callable[[], DeviceIdentity],
        on_peers_changed: Callable[[], None] | None = None,
    ) -> None:
        self.identity_provider = identity_provider
        self.on_peers_changed = on_peers_changed
        self._peers: dict[str, Peer] = {}
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []
        self._probe_thread: threading.Thread | None = None
        self._probe_lock = threading.Lock()
        self._transport = TransportClient()

    def start(self) -> None:
        """Start background discovery threads."""

        self._threads = [
            threading.Thread(target=self._broadcast_loop, name="echotext-discovery-broadcast", daemon=True),
            threading.Thread(target=self._listen_loop, name="echotext-discovery-listen", daemon=True),
        ]
        for thread in self._threads:
            thread.start()
        self.probe()

    def stop(self) -> None:
        """Stop discovery threads."""

        self._stop_event.set()
        for thread in self._threads:
            thread.join(timeout=1)

    def peers(self) -> list[Peer]:
        """Return discovered peers sorted by name."""

        return sorted(self._peers.values(), key=lambda peer: peer.name.lower())

    def probe(self) -> None:
        """Actively ask peers to identify themselves, then fall back to hello probes."""

        with self._probe_lock:
            if self._probe_thread is not None and self._probe_thread.is_alive():
                return
            self._probe_thread = threading.Thread(target=self._probe_loop, name="echotext-discovery-probe", daemon=True)
            self._probe_thread.start()

    def _broadcast_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            while not self._stop_event.is_set():
                identity = self.identity_provider()
                payload = {"magic": DISCOVERY_MAGIC, "device": dataclass_to_dict(identity)}
                payload_bytes = json.dumps(payload).encode("utf-8")
                for target in broadcast_targets(identity.hosts or (identity.host,)):
                    sock.sendto(payload_bytes, (target, DISCOVERY_PORT))
                self._stop_event.wait(2)
        finally:
            sock.close()

    def _listen_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
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
                self._handle_packet(sock, data, address)
        finally:
            sock.close()

    def _handle_packet(
        self,
        sock: socket.socket | bytes | None,
        data: bytes | str | tuple[str, int],
        address: tuple[str, int] | str | None = None,
    ) -> None:
        if isinstance(sock, bytes):
            address_value = address if address is not None else data
            self._handle_payload(None, sock, address_value)
            return
        if isinstance(data, bytes):
            self._handle_payload(sock, data, address)
            return
        return

    def _handle_payload(
        self,
        sock: socket.socket | None,
        data: bytes,
        address: tuple[str, int] | str | None,
    ) -> None:
        try:
            payload = json.loads(data.decode("utf-8"))
            magic = payload.get("magic")
            if magic == DISCOVERY_REQUEST_MAGIC:
                if sock is not None and isinstance(address, tuple):
                    self._reply_to_probe(sock, address)
                return
            if magic != DISCOVERY_MAGIC:
                return
            identity = identity_from_dict(payload["device"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return

        local_identity = self.identity_provider()
        if identity.device_id == local_identity.device_id:
            return

        source_host = address[0] if isinstance(address, tuple) else str(address or "")
        host = source_host if should_prefer_source_host(identity.host, source_host) else identity.host
        hosts = normalize_hosts(host, [source_host, *identity.hosts, identity.host])
        peer = Peer(
            device_id=identity.device_id,
            name=identity.name,
            platform=identity.platform,
            host=hosts[0],
            port=identity.port,
            hosts=hosts,
            last_seen=time.time(),
        )
        existing = self._peers.get(peer.device_id)
        self._peers[peer.device_id] = peer
        if self.on_peers_changed is None:
            return
        if existing is None or existing != peer:
            self.on_peers_changed()

    def _reply_to_probe(self, sock: socket.socket, address: tuple[str, int]) -> None:
        identity = self.identity_provider()
        payload = {"magic": DISCOVERY_MAGIC, "device": dataclass_to_dict(identity)}
        try:
            sock.sendto(json.dumps(payload).encode("utf-8"), address)
        except OSError:
            return

    def _probe_loop(self) -> None:
        self._send_discovery_requests()
        self._stop_event.wait(0.9)
        self._scan_http_peers()

    def _send_discovery_requests(self) -> None:
        identity = self.identity_provider()
        payload = json.dumps({"magic": DISCOVERY_REQUEST_MAGIC, "device_id": identity.device_id}).encode("utf-8")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            for _round in range(3):
                for target in broadcast_targets(identity.hosts or (identity.host,)):
                    try:
                        sock.sendto(payload, (target, DISCOVERY_PORT))
                    except OSError:
                        continue
                if self._stop_event.wait(0.2):
                    return
        finally:
            sock.close()

    def _scan_http_peers(self) -> None:
        identity = self.identity_provider()
        local_hosts = identity.hosts or (identity.host,)
        candidates = subnet_scan_targets(local_hosts)
        if not candidates:
            return
        found = False
        with ThreadPoolExecutor(max_workers=48) as executor:
            futures = {executor.submit(self._probe_candidate, candidate): candidate for candidate in candidates}
            for future in as_completed(futures):
                if self._stop_event.is_set():
                    return
                peer = future.result()
                if peer is None:
                    continue
                existing = self._peers.get(peer.device_id)
                self._peers[peer.device_id] = peer
                if self.on_peers_changed is not None and (existing is None or existing != peer):
                    self.on_peers_changed()
                found = True
                if found and len(self._peers) >= 1:
                    return

    def _probe_candidate(self, host: str) -> Peer | None:
        try:
            identity = self._transport.hello(host, DEFAULT_TRANSPORT_PORT, timeout=0.18)
        except TransportError:
            return None
        local_identity = self.identity_provider()
        if identity.device_id == local_identity.device_id:
            return None
        hosts = normalize_hosts(host, [*identity.hosts, identity.host])
        return Peer(
            device_id=identity.device_id,
            name=identity.name,
            platform=identity.platform,
            host=hosts[0],
            port=identity.port,
            hosts=hosts,
            last_seen=time.time(),
        )
