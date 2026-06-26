from __future__ import annotations

import sys
from pathlib import Path


def resource_root() -> Path:
    """Return the runtime root for bundled and source executions."""

    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def branding_asset(*parts: str) -> Path:
    """Return a path under the shared branding asset directory."""

    return resource_root() / "assets" / "branding" / Path(*parts)


def window_icon_path() -> Path | None:
    """Return the preferred window icon path when available."""

    candidates = ["echotext-icon-256.png", "echotext-icon-1024.png"]
    if sys.platform == "win32":
        candidates.insert(0, "EchoText.ico")
    for candidate in candidates:
        path = branding_asset(candidate)
        if path.exists():
            return path
    return None


def installer_icon_path() -> Path:
    """Return the Windows icon used by packaging scripts."""

    return branding_asset("EchoText.ico")
