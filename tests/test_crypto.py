from __future__ import annotations

import time

from echotext.crypto import PairCode, generate_shared_secret, sign_payload, verify_signature


def test_signature_round_trip() -> None:
    secret = generate_shared_secret()
    payload = {"message": {"text": "hello", "count": 1}}

    signature = sign_payload(secret, payload)

    assert verify_signature(secret, payload, signature)
    assert not verify_signature(secret, {"message": {"text": "changed", "count": 1}}, signature)


def test_pair_code_expires() -> None:
    pair_code = PairCode()
    code = pair_code.code
    pair_code._expires_at = time.time() - 1

    assert not pair_code.matches(code)
    assert pair_code.code != code
