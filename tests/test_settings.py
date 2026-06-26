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
