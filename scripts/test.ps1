$ErrorActionPreference = "Stop"

uv sync --group dev
uv run ruff format --check .
uv run ruff check .
uv run pytest

