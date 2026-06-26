from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

from echotext import settings


def test_default_data_dir_uses_android_app_storage(monkeypatch) -> None:
    android_module = ModuleType("android")
    storage_module = ModuleType("android.storage")
    storage_module.app_storage_path = lambda: "/tmp/echotext-app"

    monkeypatch.setattr(settings, "_is_android", lambda: True)
    monkeypatch.setitem(sys.modules, "android", android_module)
    monkeypatch.setitem(sys.modules, "android.storage", storage_module)

    assert settings.default_data_dir() == Path("/tmp/echotext-app") / "EchoText"


def test_language_defaults_to_chinese_on_windows(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings.platform, "system", lambda: "Windows")

    store = settings.SettingsStore(data_dir=tmp_path)

    assert store.language() == "zh"


def test_auto_sync_setting_round_trips(tmp_path: Path) -> None:
    store = settings.SettingsStore(data_dir=tmp_path)

    assert store.auto_sync_enabled() is False

    store.set_auto_sync_enabled(True)
    reloaded = settings.SettingsStore(data_dir=tmp_path)

    assert reloaded.auto_sync_enabled() is True
