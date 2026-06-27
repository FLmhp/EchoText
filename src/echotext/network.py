from __future__ import annotations

import ipaddress
import re
import socket
import subprocess
import sys
import time
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass

_IPCONFIG_CACHE_TTL_SECONDS = 15.0
_WINDOWS_INTERFACE_CACHE: tuple[float, list[_Ipv4Interface]] = (0.0, [])


@dataclass(frozen=True)
class _Ipv4Interface:
    address: str
    netmask: str
    broadcast: str


def local_lan_ip() -> str:
    """Best-effort LAN IP discovery without sending application data."""

    candidates = lan_ipv4_candidates()
    best = _best_lan_ip(candidates)
    return best or "127.0.0.1"


def lan_ipv4_candidates() -> list[str]:
    """Return valid, deduplicated IPv4 candidates for LAN communication."""

    return [candidate for candidate in _ipv4_candidates() if _lan_priority(candidate) > 0]


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
    """Return deduplicated, valid LAN hosts with the preferred host first."""

    ordered: list[str] = []
    if _is_valid_ipv4(primary_host):
        ordered.append(primary_host)
    for host in extra_hosts or ():
        if _is_valid_ipv4(host) and host not in ordered:
            ordered.append(host)
    return tuple(ordered)


def broadcast_targets(hosts: str | Iterable[str]) -> list[str]:
    """Return broadcast targets for one or more active LAN hosts."""

    targets = ["255.255.255.255"]
    host_values = [hosts] if isinstance(hosts, str) else list(hosts)
    for host in host_values:
        broadcast = _broadcast_host(host)
        if broadcast and broadcast not in targets:
            targets.append(broadcast)
    return targets


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


def _broadcast_host(host: str) -> str | None:
    for interface in _ipv4_interfaces():
        if interface.address == host:
            return interface.broadcast
    return _derived_broadcast_host(host)


def _ipv4_interfaces() -> list[_Ipv4Interface]:
    if sys.platform == "win32":
        return _windows_ipv4_interfaces()
    return []


def _windows_ipv4_interfaces() -> list[_Ipv4Interface]:
    global _WINDOWS_INTERFACE_CACHE

    now = time.monotonic()
    cached_at, cached_interfaces = _WINDOWS_INTERFACE_CACHE
    if now - cached_at < _IPCONFIG_CACHE_TTL_SECONDS:
        return cached_interfaces

    output = _run_windows_ipconfig()
    interfaces: list[_Ipv4Interface] = []
    blocks = re.split(r"\r?\n\r?\n+", output)
    for block in blocks:
        values = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", block)
        if not values:
            continue
        address = next((value for value in values if _lan_priority(value) > 0 and not _is_netmask(value)), None)
        if address is None:
            continue
        mask = next((value for value in values if _is_netmask(value)), None)
        if mask is None:
            continue
        broadcast = _broadcast_from_mask(address, mask)
        if broadcast is None:
            continue
        interfaces.append(_Ipv4Interface(address, mask, broadcast))

    _WINDOWS_INTERFACE_CACHE = (now, interfaces)
    return interfaces


def _run_windows_ipconfig() -> str:
    startupinfo = None
    creationflags = 0
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    completed = subprocess.run(
        ["ipconfig"],
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="ignore",
        startupinfo=startupinfo,
        creationflags=creationflags,
    )
    return completed.stdout


def _is_netmask(candidate: str) -> bool:
    if not _is_valid_ipv4(candidate):
        return False
    value = int(ipaddress.IPv4Address(candidate))
    bits = f"{value:032b}"
    return "01" not in bits


def _broadcast_from_mask(address: str, netmask: str) -> str | None:
    try:
        network = ipaddress.IPv4Network(f"{address}/{netmask}", strict=False)
    except ValueError:
        return None
    return str(network.broadcast_address)


def _derived_broadcast_host(host: str) -> str | None:
    if not _is_valid_ipv4(host):
        return None
    octets = host.split(".")
    return ".".join([octets[0], octets[1], octets[2], "255"])
