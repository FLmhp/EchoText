$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path "dist" | Out-Null
$archive = "dist\EchoText-source-v0.1.0.zip"
if (Test-Path -LiteralPath $archive) {
    Remove-Item -LiteralPath $archive -Force
}

$excluded = @(
    ".git",
    ".venv",
    ".buildozer",
    ".buildozer-cache",
    ".buildozer-venv",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "bin",
    "build",
    "dist"
)

$items = Get-ChildItem -Force |
    Where-Object {
        $_.Name -notin $excluded
    }

Compress-Archive -Path $items.FullName -DestinationPath $archive -Force
