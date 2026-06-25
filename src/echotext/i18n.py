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
        "no_devices": "No devices discovered",
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
        "no_devices": "未发现设备",
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
