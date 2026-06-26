from __future__ import annotations

import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from echotext.models import EnvironmentDiagnosis

DEFAULT_KIVY_FONT = "Roboto"
_WINDOWS_FONT_CANDIDATES = [
    ("msyh.ttc", "msyhbd.ttc"),
    ("NotoSansSC-VF.ttf", None),
    ("Deng.ttf", "Dengb.ttf"),
    ("simhei.ttf", None),
    ("simsun.ttc", "simsunb.ttf"),
]
_NETSH_FIELD_ALIASES = {
    "rule name": "rule_name",
    "规则名称": "rule_name",
    "enabled": "enabled",
    "已启用": "enabled",
    "profiles": "profiles",
    "配置文件": "profiles",
    "program": "program",
    "程序": "program",
    "remoteip": "remote_ip",
    "远程 ip": "remote_ip",
}
_NETSH_TRUE_VALUES = {"yes", "true", "on", "是"}
_NETSH_TOKEN_ALIASES = {
    "专用": "private",
    "公用": "public",
    "任何": "any",
    "localsubnet": "localsubnet",
}


@dataclass(frozen=True)
class FontSelection:
    """Resolved regular and bold font files for desktop CJK text."""

    regular: Path
    bold: Path


@dataclass(frozen=True)
class FirewallRuleInfo:
    """Flattened firewall rule attributes used by desktop diagnostics."""

    enabled: bool
    profiles: tuple[str, ...]
    program: str
    remote_addresses: tuple[str, ...]


def select_windows_font(fonts_dir: Path | None = None) -> FontSelection | None:
    """Return the first available Windows CJK font in priority order."""

    fonts_root = fonts_dir or Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    for regular_name, bold_name in _WINDOWS_FONT_CANDIDATES:
        regular_path = fonts_root / regular_name
        if not regular_path.exists():
            continue
        bold_path = regular_path if bold_name is None else fonts_root / bold_name
        if not bold_path.exists():
            bold_path = regular_path
        return FontSelection(regular=regular_path, bold=bold_path)
    return None


def register_windows_default_font(font_selection: FontSelection | None = None) -> bool:
    """Register a system CJK font as the Kivy default font on Windows."""

    if platform.system().lower() != "windows":
        return True

    selection = font_selection or select_windows_font()
    if selection is None:
        return False

    from kivy.core.text import LabelBase

    LabelBase.register(
        DEFAULT_KIVY_FONT,
        fn_regular=str(selection.regular),
        fn_bold=str(selection.bold),
        fn_italic=str(selection.regular),
        fn_bolditalic=str(selection.bold),
    )
    return True


def load_echo_firewall_rules() -> list[FirewallRuleInfo]:
    """Load enabled EchoText firewall rules from Windows Defender Firewall."""

    try:
        result = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", "name=EchoText LAN", "verbose"],
            capture_output=True,
            check=False,
            timeout=3,
            creationflags=_creation_flags(),
            startupinfo=_startup_info(),
        )
    except (OSError, subprocess.SubprocessError):
        return []

    output = _decode_netsh_output(result.stdout)
    if result.returncode != 0 or not output.strip():
        return []
    return _parse_netsh_rules(output)


def diagnose_desktop_environment(
    host: str,
    font_ok: bool,
    rules: list[FirewallRuleInfo] | None = None,
    executable: Path | None = None,
) -> EnvironmentDiagnosis:
    """Return persistent desktop diagnostics for font and LAN readiness."""

    active_rules = rules if rules is not None else load_echo_firewall_rules()
    executable_path = executable or Path(sys.executable)
    return build_environment_diagnosis(host, font_ok, active_rules, executable_path)


def build_environment_diagnosis(
    host: str,
    font_ok: bool,
    rules: list[FirewallRuleInfo],
    executable: Path,
) -> EnvironmentDiagnosis:
    """Combine host, font, firewall, and runtime facts into a UI warning."""

    lan_ip_ok = host != "127.0.0.1"
    enabled_rules = [rule for rule in rules if rule.enabled]
    firewall_rule_found = bool(enabled_rules)
    firewall_scope = _resolve_firewall_scope(enabled_rules)
    executable_path = _normalize_path(executable)
    current_process_allowed = any(
        _normalize_path(rule.program) == executable_path for rule in enabled_rules if rule.program
    )

    warning_key = ""
    warning_detail = ""
    if not lan_ip_ok:
        warning_key = "warning_no_lan_ip"
        warning_detail = host
    elif not font_ok:
        warning_key = "warning_missing_cjk_font"
    elif not firewall_rule_found:
        warning_key = "warning_firewall_missing"
        warning_detail = str(executable)
    elif not current_process_allowed:
        warning_key = "warning_current_process_firewall"
        warning_detail = str(executable)
    elif firewall_scope.startswith("private"):
        warning_key = "warning_firewall_private_only"
        warning_detail = firewall_scope

    return EnvironmentDiagnosis(
        lan_ip_ok=lan_ip_ok,
        font_ok=font_ok,
        firewall_rule_found=firewall_rule_found,
        firewall_scope=firewall_scope,
        warning_key=warning_key,
        warning_detail=warning_detail,
    )


def _resolve_firewall_scope(rules: list[FirewallRuleInfo]) -> str:
    if not rules:
        return "none"

    has_private = any("private" in rule.profiles for rule in rules)
    has_public = any("public" in rule.profiles for rule in rules)
    has_local_subnet = any("localsubnet" in rule.remote_addresses for rule in rules)
    has_any_remote = any("*" in rule.remote_addresses or "any" in rule.remote_addresses for rule in rules)

    if has_private and has_public and has_local_subnet:
        return "public+localsubnet"
    if has_private and has_public and has_any_remote:
        return "public+any"
    if has_private and has_public:
        return "public+custom"
    if has_private and has_local_subnet:
        return "private+localsubnet"
    if has_private:
        return "private-only"
    return "custom"


def _split_tokens(raw_value: str) -> tuple[str, ...]:
    values = []
    for token in raw_value.split(","):
        normalized = token.strip().lower()
        if not normalized:
            continue
        values.append(_NETSH_TOKEN_ALIASES.get(normalized, normalized))
    return tuple(values)


def _normalize_path(path: str | Path) -> str:
    return str(path).replace("/", "\\").lower()


def _parse_netsh_rules(output: str) -> list[FirewallRuleInfo]:
    blocks = [
        block
        for block in re.split(r"\r?\n\s*\r?\n", output.strip())
        if "Rule Name:" in block or "规则名称:" in block
    ]
    rules: list[FirewallRuleInfo] = []
    for block in blocks:
        fields: dict[str, str] = {}
        for line in block.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", maxsplit=1)
            normalized_key = _NETSH_FIELD_ALIASES.get(key.strip().lower())
            if normalized_key is None:
                continue
            fields[normalized_key] = value.strip()
        program = fields.get("program", "")
        if program.lower() == "any":
            program = ""
        rules.append(
            FirewallRuleInfo(
                enabled=fields.get("enabled", "").strip().lower() in _NETSH_TRUE_VALUES,
                profiles=_split_tokens(fields.get("profiles", "")),
                program=program,
                remote_addresses=_split_tokens(fields.get("remote_ip", "")),
            )
        )
    return rules


def _decode_netsh_output(raw_output: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "mbcs", "cp936", "gbk"):
        try:
            return raw_output.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_output.decode("utf-8", errors="replace")


def _creation_flags() -> int:
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _startup_info() -> subprocess.STARTUPINFO | None:
    if platform.system().lower() != "windows" or not hasattr(subprocess, "STARTUPINFO"):
        return None
    startup_info = subprocess.STARTUPINFO()
    startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup_info.wShowWindow = 0
    return startup_info
