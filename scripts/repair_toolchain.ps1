$ErrorActionPreference = "Stop"

$brokenShim = Join-Path $env:USERPROFILE "scoop\shims\python.bat"
if (Test-Path -LiteralPath $brokenShim) {
    Remove-Item -LiteralPath $brokenShim -Force
}

if (-not (Get-Command scoop -ErrorAction SilentlyContinue)) {
    throw "Scoop is required for this repair script."
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    scoop install python
}

if (-not (Get-Command pip -ErrorAction SilentlyContinue)) {
    scoop reset python
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    scoop install main/uv
}

uv python install 3.12

if (-not (Get-Command ruff -ErrorAction SilentlyContinue)) {
    uv tool install ruff
}

where.exe python
where.exe pip
where.exe uv
where.exe ruff
python --version
pip --version
uv --version
ruff --version
