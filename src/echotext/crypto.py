from __future__ import annotations

import hmac
import json
import secrets
import time
from hashlib import sha256
from typing import Any

PAIR_CODE_TTL_SECONDS = 300


def canonical_json(payload: dict[str, Any]) -> bytes:
    """Return a stable JSON representation for signing."""

    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def generate_shared_secret() -> str:
    """Create a new shared secret for a paired peer."""

    return secrets.token_hex(32)


def generate_pair_code() -> str:
    """Create a six digit pairing code."""

    return f"{secrets.randbelow(1_000_000):06d}"


def sign_payload(shared_secret: str, payload: dict[str, Any]) -> str:
    """Sign a payload with HMAC-SHA256."""

    digest = hmac.new(shared_secret.encode("utf-8"), canonical_json(payload), sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(shared_secret: str, payload: dict[str, Any], signature: str) -> bool:
    """Verify a payload signature without leaking timing information."""

    expected = sign_payload(shared_secret, payload)
    return hmac.compare_digest(expected, signature)


class PairCode:
    """A short lived pairing code."""

    def __init__(self) -> None:
        self._code = generate_pair_code()
        self._expires_at = time.time() + PAIR_CODE_TTL_SECONDS

    @property
    def code(self) -> str:
        """Return the active code, rotating when expired."""

        if self.expired:
            self.rotate()
        return self._code

    @property
    def expires_at(self) -> float:
        """Return the expiration timestamp."""

        return self._expires_at

    @property
    def expired(self) -> bool:
        """Return whether the code is expired."""

        return time.time() >= self._expires_at

    def rotate(self) -> str:
        """Rotate and return a fresh pairing code."""

        self._code = generate_pair_code()
        self._expires_at = time.time() + PAIR_CODE_TTL_SECONDS
        return self._code

    def matches(self, code: str) -> bool:
        """Return whether the provided code matches the active code."""

        return not self.expired and hmac.compare_digest(self._code, code.strip())
