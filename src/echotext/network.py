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


def subnet_scan_targets(hosts: Iterable[str]) -> tuple[str, ...]:
    """Return prioritized IPv4 scan targets from the active LAN subnet(s)."""

    local_hosts = [host for host in _dedupe(list(hosts)) if _is_valid_ipv4(host)]
    interface_by_host = {interface.address: interface for interface in _ipv4_interfaces()}
    targets: list[str] = []
    seen = set(local_hosts)
    remaining_budget = 8192

    for host in local_hosts:
        interface = interface_by_host.get(host)
        if interface is None:
            candidates = _scan_targets_same_24(host, max_hosts=remaining_budget)
        else:
            candidates = _scan_targets_for_interface(host, interface.netmask, max_hosts=remaining_budget)
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            targets.append(candidate)
            remaining_budget -= 1
            if remaining_budget <= 0:
                return tuple(targets)
    return tuple(targets)


def broadcast_targets(hosts: str | Iterable[str]) -> list[str]:
    """Return broadcast targets for one or more active LAN hosts."""

    targets = ["255.255.255.255"]
    host_values = [hosts] if isinstance(hosts, str) else list(hosts)
    for host in host_values:
        broadcast = _broadcast_host(host)
        if broadcast and broadcast not in targets:
            targets.append(broadcast)
        for extra_target in _legacy_private_broadcast_hosts(host):
            if extra_target not in targets:
                targets.append(extra_target)
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


def _legacy_private_broadcast_hosts(host: str) -> tuple[str, ...]:
    if not _is_valid_ipv4(host):
        return ()
    octets = host.split(".")
    first = int(octets[0])
    second = int(octets[1])
    if first == 10 or (first == 172 and 16 <= second <= 31):
        return (f"{octets[0]}.{octets[1]}.255.255",)
    return ()


def _scan_targets_same_24(host: str, max_hosts: int) -> list[str]:
    octets = host.split(".")
    prefix = ".".join(octets[:3]) + "."
    return [f"{prefix}{suffix}" for suffix in range(1, min(255, max_hosts + 1))]


def _scan_targets_for_interface(host: str, netmask: str, max_hosts: int) -> list[str]:
    try:
        network = ipaddress.IPv4Network(f"{host}/{netmask}", strict=False)
    except ValueError:
        return _scan_targets_same_24(host, max_hosts=max_hosts)

    local_address = ipaddress.IPv4Address(host)
    if network.prefixlen >= 24:
        return [str(address) for address in network.hosts() if address != local_address][:max_hosts]

    ordered_blocks = _ordered_24_blocks(network, local_address)
    results: list[str] = []
    lower = int(network.network_address)
    upper = int(network.broadcast_address)
    local_value = int(local_address)
    for block in ordered_blocks:
        block_start = max(block << 8, lower + 1)
        block_end = min((block << 8) + 254, upper - 1)
        for value in range(block_start, block_end + 1):
            if value == local_value:
                continue
            results.append(str(ipaddress.IPv4Address(value)))
            if len(results) >= max_hosts:
                return results
    return results


def _ordered_24_blocks(network: ipaddress.IPv4Network, local_address: ipaddress.IPv4Address) -> list[int]:
    start_block = int(network.network_address) >> 8
    end_block = int(network.broadcast_address) >> 8
    local_block = int(local_address) >> 8
    ordered = [local_block]
    for offset in range(1, (end_block - start_block) + 1):
        upper = local_block + offset
        lower = local_block - offset
        if upper <= end_block:
            ordered.append(upper)
        if lower >= start_block:
            ordered.append(lower)
    return ordered
