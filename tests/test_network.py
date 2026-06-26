from __future__ import annotations

from echotext.network import _best_lan_ip, broadcast_targets, should_prefer_source_host


def test_best_lan_ip_prefers_real_wlan_candidate_over_virtual_adapters() -> None:
    best = _best_lan_ip(["198.18.0.1", "172.24.240.1", "192.168.205.1", "192.168.8.1", "192.168.3.27"])

    assert best == "192.168.3.27"


def test_should_prefer_source_host_for_virtual_advertised_ip() -> None:
    assert should_prefer_source_host("198.18.0.1", "192.168.3.27")


def test_broadcast_targets_include_subnet_broadcast_after_global() -> None:
    assert broadcast_targets("192.168.3.27") == ["255.255.255.255", "192.168.3.255"]
