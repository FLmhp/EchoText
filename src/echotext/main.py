from __future__ import annotations

from kivy.config import Config

from echotext.assets import window_icon_path
from echotext.desktop_env import register_windows_default_font


def main() -> None:
    """Run the EchoText GUI."""

    register_windows_default_font()
    icon_path = window_icon_path()
    if icon_path is not None:
        Config.set("kivy", "window_icon", str(icon_path))
    from echotext.app import EchoTextApp

    EchoTextApp().run()
