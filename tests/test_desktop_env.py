from __future__ import annotations

from pathlib import Path

from echotext import desktop_env


def test_select_windows_font_uses_priority_order(tmp_path: Path) -> None:
    (tmp_path / "simhei.ttf").write_text("", encoding="utf-8")
    (tmp_path / "msyh.ttc").write_text("", encoding="utf-8")
    (tmp_path / "msyhbd.ttc").write_text("", encoding="utf-8")

    selection = desktop_env.select_windows_font(tmp_path)

    assert selection is not None
    assert selection.regular == tmp_path / "msyh.ttc"
    assert selection.bold == tmp_path / "msyhbd.ttc"


def test_select_windows_font_falls_back_to_regular_when_bold_missing(tmp_path: Path) -> None:
    (tmp_path / "Deng.ttf").write_text("", encoding="utf-8")

    selection = desktop_env.select_windows_font(tmp_path)

    assert selection is not None
    assert selection.regular == tmp_path / "Deng.ttf"
    assert selection.bold == tmp_path / "Deng.ttf"


def test_build_environment_diagnosis_accepts_public_localsubnet_scope(tmp_path: Path) -> None:
    diagnosis = desktop_env.build_environment_diagnosis(
        host="192.168.1.10",
        font_ok=True,
        rules=[
            desktop_env.FirewallRuleInfo(
                enabled=True,
                profiles=("private", "public"),
                program=str(tmp_path / "EchoText.exe"),
                remote_addresses=("localsubnet",),
            )
        ],
        executable=tmp_path / "EchoText.exe",
    )

    assert diagnosis.firewall_scope == "public+localsubnet"
    assert diagnosis.warning_key == ""


def test_build_environment_diagnosis_reports_private_only_rule(tmp_path: Path) -> None:
    diagnosis = desktop_env.build_environment_diagnosis(
        host="192.168.1.10",
        font_ok=True,
        rules=[
            desktop_env.FirewallRuleInfo(
                enabled=True,
                profiles=("private",),
                program=str(tmp_path / "EchoText.exe"),
                remote_addresses=("localsubnet",),
            )
        ],
        executable=tmp_path / "EchoText.exe",
    )

    assert diagnosis.warning_key == "warning_firewall_private_only"


def test_build_environment_diagnosis_reports_missing_firewall_rule(tmp_path: Path) -> None:
    diagnosis = desktop_env.build_environment_diagnosis(
        host="192.168.1.10",
        font_ok=True,
        rules=[],
        executable=tmp_path / "EchoText.exe",
    )

    assert diagnosis.warning_key == "warning_firewall_missing"


def test_build_environment_diagnosis_reports_loopback_host(tmp_path: Path) -> None:
    diagnosis = desktop_env.build_environment_diagnosis(
        host="127.0.0.1",
        font_ok=True,
        rules=[
            desktop_env.FirewallRuleInfo(
                enabled=True,
                profiles=("private", "public"),
                program=str(tmp_path / "EchoText.exe"),
                remote_addresses=("localsubnet",),
            )
        ],
        executable=tmp_path / "EchoText.exe",
    )

    assert diagnosis.warning_key == "warning_no_lan_ip"


def test_build_environment_diagnosis_reports_current_process_not_allowed(tmp_path: Path) -> None:
    diagnosis = desktop_env.build_environment_diagnosis(
        host="192.168.1.10",
        font_ok=True,
        rules=[
            desktop_env.FirewallRuleInfo(
                enabled=True,
                profiles=("private", "public"),
                program=str(tmp_path / "EchoText.exe"),
                remote_addresses=("localsubnet",),
            )
        ],
        executable=tmp_path / "python.exe",
    )

    assert diagnosis.warning_key == "warning_current_process_firewall"


def test_parse_netsh_rules_reads_program_and_scope() -> None:
    output = """
Rule Name:                            EchoText LAN
----------------------------------------------------------------------
Enabled:                              Yes
Profiles:                             Private,Public
RemoteIP:                             LocalSubnet
Program:                              C:\\Program Files\\EchoText\\EchoText.exe
Action:                               Allow
Ok.
"""

    rules = desktop_env._parse_netsh_rules(output)

    assert rules == [
        desktop_env.FirewallRuleInfo(
            enabled=True,
            profiles=("private", "public"),
            program=r"C:\Program Files\EchoText\EchoText.exe",
            remote_addresses=("localsubnet",),
        )
    ]


def test_parse_netsh_rules_supports_utf8_chinese_labels() -> None:
    output = desktop_env._decode_netsh_output(
        (
            "\r\n规则名称:                             EchoText LAN\r\n"
            "----------------------------------------------------------------------\r\n"
            "已启用:                               是\r\n"
            "方向:                                 入\r\n"
            "配置文件:                             专用,公用\r\n"
            "远程 IP:                              LocalSubnet\r\n"
            "程序:                                 C:\\Program Files\\EchoText\\EchoText.exe\r\n"
            "操作:                                 允许\r\n"
        ).encode()
    )

    rules = desktop_env._parse_netsh_rules(output)

    assert rules == [
        desktop_env.FirewallRuleInfo(
            enabled=True,
            profiles=("private", "public"),
            program=r"C:\Program Files\EchoText\EchoText.exe",
            remote_addresses=("localsubnet",),
        )
    ]
