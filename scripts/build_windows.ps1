$ErrorActionPreference = "Stop"

uv sync --group dev
uv run python scripts/generate_brand_assets.py
uv run pyinstaller --clean --noconfirm packaging/echotext_pyinstaller.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $iscc) {
    $candidates = @(
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            $iscc = Get-Item -LiteralPath $candidate
            break
        }
    }
}

if (-not $iscc) {
    Write-Warning "Inno Setup ISCC.exe was not found. Install it with: winget install --id JRSoftware.InnoSetup -e"
    exit 2
}

$isccPath = if ($iscc.Source) { $iscc.Source } else { $iscc.FullName }
& $isccPath "packaging\echotext.iss"
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE"
}
