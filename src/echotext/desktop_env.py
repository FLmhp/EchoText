from __future__ import annotations

import json
import os
import platform
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

    script = """
$rules = Get-NetFirewallRule -DisplayName 'EchoText LAN' -ErrorAction SilentlyContinue
if (-not $rules) {
    '[]'
    exit 0
}
$rules | ForEach-Object {
    $application = $_ | Get-NetFirewallApplicationFilter
    $address = $_ | Get-NetFirewallAddressFilter
    [pscustomobject]@{
        Enabled = [bool]($_.Enabled -eq 'True')
        Profile = [string]$_.Profile
        Program = [string]$application.Program
        RemoteAddress = [string]$address.RemoteAddress
    }
} | ConvertTo-Json -Compress
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            check=False,
            encoding="utf-8",
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return []

    if result.returncode != 0 or not result.stdout.strip():
        return []

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    rows = payload if isinstance(payload, list) else [payload]
    rules: list[FirewallRuleInfo] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        rules.append(
            FirewallRuleInfo(
                enabled=bool(row.get("Enabled", False)),
                profiles=_split_tokens(str(row.get("Profile", ""))),
                program=str(row.get("Program", "")),
                remote_addresses=_split_tokens(str(row.get("RemoteAddress", ""))),
            )
        )
    return rules


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
    values = [token.strip().lower() for token in raw_value.split(",") if token.strip()]
    return tuple(values)


def _normalize_path(path: str | Path) -> str:
    return str(path).replace("/", "\\").lower()
