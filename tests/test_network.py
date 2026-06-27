from __future__ import annotations

from echotext import network
from echotext.network import (
    _best_lan_ip,
    broadcast_targets,
    normalize_hosts,
    should_prefer_source_host,
    subnet_scan_targets,
)


def test_best_lan_ip_prefers_real_wlan_candidate_over_virtual_adapters() -> None:
    best = _best_lan_ip(["198.18.0.1", "172.24.240.1", "192.168.205.1", "192.168.8.1", "192.168.3.27"])

    assert best == "192.168.3.27"


def test_should_prefer_source_host_for_virtual_advertised_ip() -> None:
    assert should_prefer_source_host("198.18.0.1", "192.168.3.27")


def test_broadcast_targets_include_subnet_broadcast_after_global() -> None:
    assert broadcast_targets("192.168.3.27") == ["255.255.255.255", "192.168.3.255"]


def test_broadcast_targets_include_each_known_subnet() -> None:
    assert broadcast_targets(["192.168.3.27", "10.127.107.72"]) == [
        "255.255.255.255",
        "192.168.3.255",
        "10.127.107.255",
        "10.127.255.255",
    ]


def test_broadcast_targets_use_actual_windows_subnet_mask(monkeypatch) -> None:
    monkeypatch.setattr(network.sys, "platform", "win32")
    monkeypatch.setattr(
        network,
        "_run_windows_ipconfig",
        lambda: (
            """
Wireless LAN adapter WLAN:

   IPv4 Address. . . . . . . . . . . : 172.21.114.240
   Subnet Mask . . . . . . . . . . . : 255.255.128.0
   Default Gateway . . . . . . . . . : 172.21.0.1
"""
        ),
    )
    monkeypatch.setattr(network, "_WINDOWS_INTERFACE_CACHE", (0.0, []))

    assert broadcast_targets("172.21.114.240") == ["255.255.255.255", "172.21.127.255", "172.21.255.255"]


def test_normalize_hosts_keeps_primary_and_deduplicates() -> None:
    assert normalize_hosts("172.21.100.161", ["10.127.107.72", "172.21.100.161", "bad-host"]) == (
        "172.21.100.161",
        "10.127.107.72",
    )


def test_subnet_scan_targets_expand_across_real_windows_subnet(monkeypatch) -> None:
    monkeypatch.setattr(network.sys, "platform", "win32")
    monkeypatch.setattr(
        network,
        "_run_windows_ipconfig",
        lambda: (
            """
Wireless LAN adapter WLAN:

   IPv4 Address. . . . . . . . . . . : 172.21.114.240
   Subnet Mask . . . . . . . . . . . : 255.255.128.0
   Default Gateway . . . . . . . . . : 172.21.0.1
"""
        ),
    )
    monkeypatch.setattr(network, "_WINDOWS_INTERFACE_CACHE", (0.0, []))

    targets = subnet_scan_targets(["172.21.114.240"])

    assert "172.21.100.161" in targets
    assert targets.index("172.21.114.1") < targets.index("172.21.100.161")
