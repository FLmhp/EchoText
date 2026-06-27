from __future__ import annotations

from echotext.network import (
    _best_lan_ip,
    broadcast_targets,
    format_http_host,
    lan_ipv4_candidates,
    normalize_hosts,
    parse_host_endpoint,
    should_prefer_source_host,
    subnet_scan_targets,
)


def test_best_lan_ip_prefers_real_wlan_candidate_over_virtual_adapters() -> None:
    best = _best_lan_ip(["198.18.0.1", "172.24.240.1", "192.168.205.1", "192.168.8.1", "192.168.3.27"])

    assert best == "192.168.3.27"


def test_lan_ipv4_candidates_are_sorted_by_preferred_real_network(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "echotext.network._ipv4_candidates",
        lambda: ["172.28.80.1", "192.168.205.1", "192.168.8.1", "192.168.3.27"],
    )

    assert lan_ipv4_candidates() == ["192.168.3.27", "192.168.205.1", "192.168.8.1", "172.28.80.1"]


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


def test_normalize_hosts_keeps_ipv6_literals() -> None:
    assert normalize_hosts("2403:ac00:b101:387::1234", ["[2403:ac00:b101:387::1234]", "192.168.3.27"]) == (
        "2403:ac00:b101:387::1234",
        "192.168.3.27",
    )


def test_subnet_scan_targets_follow_reference_same_24_scan() -> None:
    targets = subnet_scan_targets(["172.21.114.240"])

    assert "172.21.114.1" in targets
    assert "172.21.114.254" in targets
    assert "172.21.100.161" not in targets


def test_parse_host_endpoint_supports_ipv4_and_ipv6() -> None:
    assert parse_host_endpoint("192.168.3.27:48735").host == "192.168.3.27"
    assert parse_host_endpoint("192.168.3.27:48735").port == 48735
    assert parse_host_endpoint("[2403:ac00:b101:387::1234]:5000").host == "2403:ac00:b101:387::1234"
    assert parse_host_endpoint("[2403:ac00:b101:387::1234]:5000").port == 5000
    assert parse_host_endpoint("2403:ac00:b101:387::1234").port == 48735


def test_format_http_host_brackets_ipv6() -> None:
    assert format_http_host("192.168.3.27") == "192.168.3.27"
    assert format_http_host("2403:ac00:b101:387::1234") == "[2403:ac00:b101:387::1234]"
