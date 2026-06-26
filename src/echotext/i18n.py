from __future__ import annotations

import locale

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "title": "EchoText",
        "pair_code": "Pair code",
        "refresh": "Refresh",
        "pair": "Pair",
        "paste": "Paste",
        "send": "Send",
        "copy_latest": "Copy latest",
        "clear": "Clear",
        "auto_sync": "Foreground auto sync",
        "persistent_history": "Save local history",
        "language": "Language",
        "message": "Message",
        "devices": "Devices",
        "pair_code_hint": "Target pair code",
        "status_ready": "Ready",
        "status_sent": "Sent",
        "status_paired": "Paired",
        "status_failed": "Failed",
        "status_select_device": "Select a device first",
        "status_enter_pair_code": "Enter the target pair code",
        "status_enter_message": "Enter a message first",
        "status_nothing_to_copy": "No message available to copy",
        "status_history_cleared": "History cleared",
        "status_clipboard_unavailable": "Clipboard is unavailable",
        "status_clipboard_empty": "Clipboard is empty",
        "no_devices": "No devices discovered",
        "paired_suffix": " · paired",
        "language_auto": "System",
        "language_english": "English",
        "language_chinese": "Chinese",
        "warning_no_lan_ip": "No LAN IP detected. Current host: {detail}",
        "warning_missing_cjk_font": "No supported Chinese system font was found. Chinese text may render incorrectly.",
        "warning_firewall_missing": "Windows has not allowed LAN access for this process: {detail}",
        "warning_current_process_firewall": "The current process is not covered by the EchoText firewall rule: {detail}",
        "warning_firewall_private_only": "The installed firewall rule only allows Private networks. Reinstall the latest desktop package.",
    },
    "zh": {
        "title": "EchoText",
        "pair_code": "配对码",
        "refresh": "刷新",
        "pair": "配对",
        "paste": "粘贴",
        "send": "发送",
        "copy_latest": "复制最新",
        "clear": "清空",
        "auto_sync": "前台自动同步",
        "persistent_history": "保存本地历史",
        "language": "语言",
        "message": "消息",
        "devices": "设备",
        "pair_code_hint": "目标配对码",
        "status_ready": "就绪",
        "status_sent": "已发送",
        "status_paired": "已配对",
        "status_failed": "失败",
        "status_select_device": "请先选择设备",
        "status_enter_pair_code": "请输入目标配对码",
        "status_enter_message": "请先输入消息",
        "status_nothing_to_copy": "当前没有可复制的消息",
        "status_history_cleared": "历史记录已清空",
        "status_clipboard_unavailable": "剪贴板不可用",
        "status_clipboard_empty": "剪贴板为空",
        "no_devices": "未发现设备",
        "paired_suffix": " · 已配对",
        "language_auto": "跟随系统",
        "language_english": "English",
        "language_chinese": "中文",
        "warning_no_lan_ip": "当前未获取到可用局域网地址，当前主机地址：{detail}",
        "warning_missing_cjk_font": "当前系统未找到受支持的中文字体，中文界面可能显示异常。",
        "warning_firewall_missing": "Windows 尚未为当前进程开放局域网访问：{detail}",
        "warning_current_process_firewall": "当前运行进程不在 EchoText 防火墙规则内：{detail}",
        "warning_firewall_private_only": "已安装的防火墙规则仅允许 Private 网络，请重装最新版桌面端安装包。",
    },
}


def resolve_language(preference: str) -> str:
    """Resolve a language preference to a supported language."""

    if preference in TRANSLATIONS:
        return preference
    language, _encoding = locale.getlocale()
    if language and language.lower().startswith("zh"):
        return "zh"
    return "en"


def translator(preference: str):
    """Return a translation function."""

    language = resolve_language(preference)

    def translate(key: str) -> str:
        return TRANSLATIONS[language].get(key, TRANSLATIONS["en"].get(key, key))

    return translate
