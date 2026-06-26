from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    """Make the local ``src`` tree importable in bundled source-only runs."""

    project_root = Path(__file__).resolve().parent
    src_dir = project_root / "src"
    if src_dir.is_dir():
        src_path = str(src_dir)
        if src_path not in sys.path:
            sys.path.insert(0, src_path)


_ensure_src_on_path()


def main() -> None:
    from echotext.main import main as echotext_main

    echotext_main()


if __name__ == "__main__":
    main()
