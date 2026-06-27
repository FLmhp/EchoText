from __future__ import annotations

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
    assert broadcast_targets("192.168.3.27") == ["255.255.255.255", "192.168.3.255", "192.168.255.255"]


def test_broadcast_targets_include_each_known_subnet() -> None:
    assert broadcast_targets(["192.168.3.27", "10.127.107.72"]) == [
        "255.255.255.255",
        "192.168.3.255",
        "10.127.107.255",
        "192.168.255.255",
        "10.127.255.255",
    ]


def test_broadcast_targets_follow_reference_24_and_16_prefixes() -> None:
    assert broadcast_targets("172.21.114.240") == ["255.255.255.255", "172.21.114.255", "172.21.255.255"]


def test_normalize_hosts_keeps_primary_and_deduplicates() -> None:
    assert normalize_hosts("172.21.100.161", ["10.127.107.72", "172.21.100.161", "bad-host"]) == (
        "172.21.100.161",
        "10.127.107.72",
    )


def test_subnet_scan_targets_follow_reference_same_24_scan() -> None:
    targets = subnet_scan_targets(["172.21.114.240"])

    assert "172.21.114.1" in targets
    assert "172.21.114.254" in targets
    assert "172.21.100.161" not in targets
