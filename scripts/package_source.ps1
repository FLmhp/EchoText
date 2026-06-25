$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path "dist" | Out-Null
$archive = "dist\EchoText-source-v0.1.0.zip"
if (Test-Path -LiteralPath $archive) {
    Remove-Item -LiteralPath $archive -Force
}

$items = Get-ChildItem -Force |
    Where-Object {
        $_.Name -notin @(".git", ".venv", ".buildozer", "build", "dist", "__pycache__")
    }

Compress-Archive -Path $items.FullName -DestinationPath $archive -Force

