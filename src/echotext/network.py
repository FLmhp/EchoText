from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass

_PROBE_TARGETS = ("8.8.8.8", "114.114.114.114")
DEFAULT_ECHOTEXT_PORT = 48735


@dataclass(frozen=True)
class HostEndpoint:
    """A parsed IP endpoint for direct peer access."""

    host: str
    port: int = DEFAULT_ECHOTEXT_PORT


def local_lan_ip() -> str:
    """Return the best currently reachable IPv4 LAN address."""

    candidates = lan_ipv4_candidates()
    best = _best_lan_ip(candidates)
    return best or "127.0.0.1"


def lan_ipv4_candidates() -> list[str]:
    """Return valid IPv4 candidates discovered from the real network."""

    candidates = [candidate for candidate in _ipv4_candidates() if _lan_priority(candidate) > 0]
    return sorted(candidates, key=_lan_sort_key, reverse=True)


def lan_ipv6_candidates() -> list[str]:
    """Return non-link-local IPv6 candidates that can be shared directly."""

    candidates = [candidate for candidate in _ipv6_candidates() if _is_good_ipv6(candidate)]
    return sorted(_dedupe(candidates), key=_ipv6_sort_key, reverse=True)


def should_prefer_source_host(advertised_host: str, source_host: str) -> bool:
    """Return whether discovery should trust the packet source over the advertised host."""

    if not _is_valid_ipv4(source_host):
        return False
    if not _is_valid_ipv4(advertised_host):
        return True
    advertised_score = _lan_priority(advertised_host)
    source_score = _lan_priority(source_host)
    return source_score > advertised_score


def normalize_hosts(primary_host: str, extra_hosts: Iterable[str] | None = None) -> tuple[str, ...]:
    """Return deduplicated IP hosts with the preferred host first."""

    ordered: list[str] = []
    normalized_primary = _normalize_ip_literal(primary_host)
    if normalized_primary is not None:
        ordered.append(normalized_primary)
    for host in extra_hosts or ():
        normalized_host = _normalize_ip_literal(host)
        if normalized_host is not None and normalized_host not in ordered:
            ordered.append(normalized_host)
    return tuple(ordered)


def parse_host_endpoint(value: str, default_port: int = DEFAULT_ECHOTEXT_PORT) -> HostEndpoint:
    """Parse a manual direct-connect IP input into a host and port."""

    raw = value.strip()
    if not raw:
        raise ValueError("empty endpoint")

    if raw.startswith("["):
        closing = raw.find("]")
        if closing < 0:
            raise ValueError("invalid IPv6 endpoint")
        host = raw[1:closing].strip()
        remainder = raw[closing + 1 :].strip()
        if not remainder:
            port = default_port
        elif remainder.startswith(":") and remainder[1:].isdigit():
            port = int(remainder[1:])
        else:
            raise ValueError("invalid endpoint port")
    elif raw.count(":") > 1:
        host = raw
        port = default_port
    elif ":" in raw:
        host, port_text = raw.rsplit(":", maxsplit=1)
        if not port_text.isdigit():
            raise ValueError("invalid endpoint port")
        port = int(port_text)
    else:
        host = raw
        port = default_port

    normalized_host = _normalize_ip_literal(host)
    if normalized_host is None:
        raise ValueError("invalid IP address")
    if port < 1 or port > 65535:
        raise ValueError("invalid endpoint port")
    return HostEndpoint(normalized_host, port)


def format_http_host(host: str) -> str:
    """Return an HTTP-safe host literal, bracketing IPv6 when required."""

    normalized_host = _normalize_ip_literal(host)
    if normalized_host is None:
        raise ValueError("invalid IP address")
    if ":" in normalized_host:
        return f"[{normalized_host}]"
    return normalized_host


def broadcast_targets(hosts: str | Iterable[str]) -> list[str]:
    """Return reference-style discovery broadcast targets for the current IPv4 hosts."""

    targets = ["255.255.255.255"]
    host_values = [hosts] if isinstance(hosts, str) else list(hosts)
    for prefix in _ipv4_prefixes_24(host_values):
        target = f"{prefix}255"
        if target not in targets:
            targets.append(target)
    for prefix in _ipv4_prefixes_16(host_values):
        target = f"{prefix}255.255"
        if target not in targets:
            targets.append(target)
    return targets


def subnet_scan_targets(hosts: Iterable[str]) -> tuple[str, ...]:
    """Return same-segment IPv4 scan targets using /24 prefixes like the reference app."""

    local_hosts = set(normalize_hosts("", hosts))
    targets: list[str] = []
    for prefix in _ipv4_prefixes_24(local_hosts):
        for suffix in range(1, 255):
            candidate = f"{prefix}{suffix}"
            if candidate not in local_hosts and candidate not in targets:
                targets.append(candidate)
    return tuple(targets)


def _ipv4_candidates() -> list[str]:
    candidates: list[str] = []
    candidates.extend(_probe_ips())

    hostname = socket.gethostname()
    try:
        _host, _aliases, addresses = socket.gethostbyname_ex(hostname)
        candidates.extend(addresses)
    except OSError:
        pass

    with suppress(OSError):
        candidates.extend(item[4][0] for item in socket.getaddrinfo(hostname, None, socket.AF_INET))

    return _dedupe([candidate for candidate in candidates if _is_good_ipv4(candidate)])


def _ipv6_candidates() -> list[str]:
    candidates: list[str] = []
    hostname = socket.gethostname()
    with suppress(OSError):
        for item in socket.getaddrinfo(hostname, None, socket.AF_INET6):
            normalized = _normalize_ipv6(item[4][0])
            if normalized is None:
                continue
            if normalized == "::1" or normalized.lower().startswith("fe80:"):
                continue
            candidates.append(normalized)
    return _dedupe(candidates)


def _probe_ips() -> list[str]:
    ips: list[str] = []
    for target in _PROBE_TARGETS:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect((target, 80))
            ips.append(str(probe.getsockname()[0]))
        except OSError:
            continue
        finally:
            probe.close()
    return ips


def _ipv4_prefixes_24(hosts: Iterable[str]) -> list[str]:
    prefixes: list[str] = []
    for host in hosts:
        if not _is_valid_ipv4(host):
            continue
        octets = host.split(".")
        prefix = ".".join(octets[:3]) + "."
        if prefix not in prefixes:
            prefixes.append(prefix)
    return prefixes


def _ipv4_prefixes_16(hosts: Iterable[str]) -> list[str]:
    prefixes: list[str] = []
    for host in hosts:
        if not _is_valid_ipv4(host):
            continue
        octets = host.split(".")
        prefix = ".".join(octets[:2]) + "."
        if prefix not in prefixes:
            prefixes.append(prefix)
    return prefixes


def _best_lan_ip(candidates: list[str]) -> str | None:
    scored = [candidate for candidate in candidates if _lan_priority(candidate) > 0]
    if not scored:
        return None
    return max(scored, key=_lan_priority)


def _lan_sort_key(candidate: str) -> tuple[int, int]:
    return (_lan_priority(candidate), 1 if candidate.startswith("192.168.") else 0)


def _ipv6_sort_key(candidate: str) -> tuple[int, int]:
    try:
        address = ipaddress.IPv6Address(candidate)
    except ipaddress.AddressValueError:
        return (0, 0)
    return (2 if address.is_private else 1, 1 if not address.teredo else 0)


def _lan_priority(candidate: str) -> int:
    if not _is_valid_ipv4(candidate):
        return 0

    address = ipaddress.IPv4Address(candidate)
    if address.is_loopback or address.is_link_local or address.is_multicast or address.is_unspecified:
        return 0

    score = 10
    if address in ipaddress.IPv4Network("192.168.0.0/16"):
        score = 100
    elif address in ipaddress.IPv4Network("10.0.0.0/8"):
        score = 90
    elif address in ipaddress.IPv4Network("172.16.0.0/12"):
        score = 80
    elif address in ipaddress.IPv4Network("198.18.0.0/15"):
        score = -40
    elif address.is_global:
        score = 40

    if int(candidate.rsplit(".", maxsplit=1)[1]) == 1:
        score -= 45
    return score


def _is_good_ipv4(candidate: str) -> bool:
    if not _is_valid_ipv4(candidate):
        return False
    return not candidate.startswith("127.") and not candidate.startswith("169.254.")


def _is_good_ipv6(candidate: str) -> bool:
    normalized = _normalize_ipv6(candidate)
    if normalized is None:
        return False
    address = ipaddress.IPv6Address(normalized)
    return not (address.is_loopback or address.is_link_local or address.is_multicast or address.is_unspecified)


def _is_valid_ipv4(candidate: str) -> bool:
    try:
        ipaddress.IPv4Address(candidate)
    except ipaddress.AddressValueError:
        return False
    return True


def _normalize_ipv6(candidate: str) -> str | None:
    stripped = candidate.strip().strip("[]")
    if "%" in stripped:
        stripped = stripped.split("%", maxsplit=1)[0]
    try:
        address = ipaddress.IPv6Address(stripped)
    except ipaddress.AddressValueError:
        return None
    if address.ipv4_mapped is not None:
        return str(address.ipv4_mapped)
    return str(address)


def _normalize_ip_literal(candidate: str) -> str | None:
    stripped = candidate.strip()
    if not stripped:
        return None
    if _is_valid_ipv4(stripped):
        return stripped
    return _normalize_ipv6(stripped)


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
