from __future__ import annotations

from echotext.desktop_env import register_windows_default_font


def main() -> None:
    """Run the EchoText GUI."""

    register_windows_default_font()
    from echotext.app import EchoTextApp

    EchoTextApp().run()
