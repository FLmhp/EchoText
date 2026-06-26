from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from echotext.crypto import sign_payload, verify_signature
from echotext.models import DeviceIdentity, Peer, TextMessage
from echotext.serialization import dataclass_to_dict, identity_from_dict, message_from_dict

DEFAULT_TRANSPORT_PORT = 48735


class TransportError(RuntimeError):
    """Raised when a peer request fails."""


class EchoRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for EchoText peers."""

    server: EchoHTTPServer

    def log_message(self, _format: str, *_args: Any) -> None:
        """Silence the default HTTP server logging."""

    def do_GET(self) -> None:
        """Serve identity metadata."""

        if self.path != "/api/v1/hello":
            self._write_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        self._write_json({"device": dataclass_to_dict(self.server.identity_provider())})

    def do_POST(self) -> None:
        """Handle pairing and message endpoints."""

        try:
            payload = self._read_json()
        except ValueError:
            self._write_json({"error": "invalid_json"}, HTTPStatus.BAD_REQUEST)
            return

        if self.path == "/api/v1/pair":
            self._handle_pair(payload)
            return
        if self.path == "/api/v1/messages":
            self._handle_message(payload)
            return
        self._write_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def _handle_pair(self, payload: dict[str, Any]) -> None:
        try:
            peer_identity = identity_from_dict(payload["device"])
            pair_code = str(payload["pair_code"])
            shared_secret = str(payload["shared_secret"])
        except (KeyError, TypeError, ValueError):
            self._write_json({"error": "invalid_pair_payload"}, HTTPStatus.BAD_REQUEST)
            return

        if not self.server.pair_code_matches(pair_code):
            self._write_json({"error": "pair_code_rejected"}, HTTPStatus.FORBIDDEN)
            return

        peer = Peer(
            device_id=peer_identity.device_id,
            name=peer_identity.name,
            platform=peer_identity.platform,
            host=peer_identity.host,
            port=peer_identity.port,
            last_seen=time.time(),
            shared_secret=shared_secret,
        )
        self.server.on_peer_paired(peer)
        self._write_json({"ok": True, "device": dataclass_to_dict(self.server.identity_provider())})

    def _handle_message(self, payload: dict[str, Any]) -> None:
        try:
            message = message_from_dict(payload["message"])
        except (KeyError, TypeError, ValueError):
            self._write_json({"error": "invalid_message_payload"}, HTTPStatus.BAD_REQUEST)
            return

        peer = self.server.peer_provider(message.sender_id)
        if peer is None or peer.shared_secret is None:
            self._write_json({"error": "peer_not_paired"}, HTTPStatus.FORBIDDEN)
            return

        signature = self.headers.get("X-EchoText-Signature", "")
        if not verify_signature(peer.shared_secret, payload, signature):
            self._write_json({"error": "invalid_signature"}, HTTPStatus.FORBIDDEN)
            return

        self.server.on_message(message, peer)
        self._write_json({"ok": True})

    def _read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")
        return payload

    def _write_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class EchoHTTPServer(ThreadingHTTPServer):
    """HTTP server carrying runtime callbacks."""

    def __init__(
        self,
        address: tuple[str, int],
        identity_provider: Callable[[], DeviceIdentity],
        pair_code_matches: Callable[[str], bool],
        peer_provider: Callable[[str], Peer | None],
        on_message: Callable[[TextMessage, Peer], None],
        on_peer_paired: Callable[[Peer], None],
    ) -> None:
        super().__init__(address, EchoRequestHandler)
        self.identity_provider = identity_provider
        self.pair_code_matches = pair_code_matches
        self.peer_provider = peer_provider
        self.on_message = on_message
        self.on_peer_paired = on_peer_paired


class TransportServer:
    """Background HTTP server wrapper."""

    def __init__(
        self,
        identity_provider: Callable[[], DeviceIdentity],
        pair_code_matches: Callable[[str], bool],
        peer_provider: Callable[[str], Peer | None],
        on_message: Callable[[TextMessage, Peer], None],
        on_peer_paired: Callable[[Peer], None],
        preferred_port: int = DEFAULT_TRANSPORT_PORT,
    ) -> None:
        self._server = _bind_server(
            preferred_port,
            identity_provider,
            pair_code_matches,
            peer_provider,
            on_message,
            on_peer_paired,
        )
        self._thread = threading.Thread(target=self._server.serve_forever, name="echotext-http", daemon=True)

    @property
    def port(self) -> int:
        """Return the bound local port."""

        return int(self._server.server_port)

    def start(self) -> None:
        """Start serving requests."""

        self._thread.start()

    def stop(self) -> None:
        """Stop serving requests."""

        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)


def _bind_server(
    preferred_port: int,
    identity_provider: Callable[[], DeviceIdentity],
    pair_code_matches: Callable[[str], bool],
    peer_provider: Callable[[str], Peer | None],
    on_message: Callable[[TextMessage, Peer], None],
    on_peer_paired: Callable[[Peer], None],
) -> EchoHTTPServer:
    try:
        return EchoHTTPServer(
            ("", preferred_port),
            identity_provider,
            pair_code_matches,
            peer_provider,
            on_message,
            on_peer_paired,
        )
    except OSError:
        return EchoHTTPServer(
            ("", 0),
            identity_provider,
            pair_code_matches,
            peer_provider,
            on_message,
            on_peer_paired,
        )


class TransportClient:
    """HTTP client for peer operations."""

    def pair(self, peer: Peer, identity: DeviceIdentity, pair_code: str, shared_secret: str) -> DeviceIdentity:
        """Pair with a peer using the target device's visible code."""

        payload = {
            "device": dataclass_to_dict(identity),
            "pair_code": pair_code,
            "shared_secret": shared_secret,
        }
        response = self._post(peer, "/api/v1/pair", payload)
        return identity_from_dict(response["device"])

    def send_message(self, peer: Peer, message: TextMessage) -> None:
        """Send a signed message to a paired peer."""

        if peer.shared_secret is None:
            raise TransportError("Peer is not paired")
        payload = {"message": dataclass_to_dict(message)}
        headers = {"X-EchoText-Signature": sign_payload(peer.shared_secret, payload)}
        self._post(peer, "/api/v1/messages", payload, headers=headers)

    def _post(self, peer: Peer, path: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> Any:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"http://{peer.host}:{peer.port}{path}",
            data=body,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                **(headers or {}),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                data = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise TransportError(f"Peer returned HTTP {exc.code}: {error_body}") from exc
        except OSError as exc:
            raise TransportError(str(exc)) from exc
        return json.loads(data)
