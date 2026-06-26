from __future__ import annotations

import ipaddress
import socket
from contextlib import suppress


def local_lan_ip() -> str:
    """Best-effort LAN IP discovery without sending application data."""

    candidates = _ipv4_candidates()
    best = _best_lan_ip(candidates)
    return best or "127.0.0.1"


def should_prefer_source_host(advertised_host: str, source_host: str) -> bool:
    """Return whether discovery should trust the packet source over the advertised host."""

    if not _is_valid_ipv4(source_host):
        return False
    if not _is_valid_ipv4(advertised_host):
        return True
    advertised_score = _lan_priority(advertised_host)
    source_score = _lan_priority(source_host)
    return source_score > advertised_score


def _ipv4_candidates() -> list[str]:
    candidates: list[str] = []
    probe_ip = _probe_ip()
    if probe_ip is not None:
        candidates.append(probe_ip)

    hostname = socket.gethostname()
    try:
        _host, _aliases, addresses = socket.gethostbyname_ex(hostname)
        candidates.extend(addresses)
    except OSError:
        pass

    with suppress(OSError):
        candidates.extend(item[4][0] for item in socket.getaddrinfo(hostname, None, socket.AF_INET))

    return _dedupe(candidates)


def _probe_ip() -> str | None:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return str(probe.getsockname()[0])
    except OSError:
        return None
    finally:
        probe.close()


def _best_lan_ip(candidates: list[str]) -> str | None:
    scored = [candidate for candidate in candidates if _lan_priority(candidate) > 0]
    if not scored:
        return None
    return max(scored, key=_lan_priority)


def _lan_priority(candidate: str) -> int:
    if not _is_valid_ipv4(candidate):
        return 0

    address = ipaddress.IPv4Address(candidate)
    if address.is_loopback or address.is_link_local or address.is_multicast or address.is_unspecified:
        return 0

    score = 0
    if address in ipaddress.IPv4Network("192.168.0.0/16"):
        score += 100
    elif address in ipaddress.IPv4Network("10.0.0.0/8"):
        score += 90
    elif address in ipaddress.IPv4Network("172.16.0.0/12"):
        score += 80
    elif address.is_private:
        score += 60
    elif address.is_global:
        score += 40
    else:
        score += 10

    if address in ipaddress.IPv4Network("198.18.0.0/15"):
        score -= 100
    if int(candidate.rsplit(".", maxsplit=1)[1]) == 1:
        score -= 45
    return score


def _is_valid_ipv4(candidate: str) -> bool:
    try:
        ipaddress.IPv4Address(candidate)
    except ipaddress.AddressValueError:
        return False
    return True


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
