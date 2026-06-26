from __future__ import annotations

from kivy.config import Config
from kivy.utils import platform as kivy_platform

from echotext.assets import window_icon_path
from echotext.desktop_env import register_windows_default_font

DEFAULT_DESKTOP_WIDTH = 1180
DEFAULT_DESKTOP_HEIGHT = 860


def _configure_desktop_window() -> None:
    """Set a desktop-friendly default window size before Kivy boots."""

    if kivy_platform == "android":
        return
    Config.set("graphics", "width", str(DEFAULT_DESKTOP_WIDTH))
    Config.set("graphics", "height", str(DEFAULT_DESKTOP_HEIGHT))
    Config.set("graphics", "minimum_width", str(DEFAULT_DESKTOP_WIDTH))
    Config.set("graphics", "minimum_height", str(DEFAULT_DESKTOP_HEIGHT))


def main() -> None:
    """Run the EchoText GUI."""

    _configure_desktop_window()
    register_windows_default_font()
    icon_path = window_icon_path()
    if icon_path is not None:
        Config.set("kivy", "window_icon", str(icon_path))
    from echotext.app import EchoTextApp

    EchoTextApp().run()
