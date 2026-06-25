$ErrorActionPreference = "Stop"

$repo = (Resolve-Path ".").Path
$wslRepo = $repo -replace "^([A-Za-z]):", "/mnt/`$1" -replace "\\", "/"
$wslRepo = $wslRepo.ToLowerInvariant()

wsl.exe -d Ubuntu -- bash -lc "command -v java >/dev/null && python3 -m pip --version >/dev/null"
if ($LASTEXITCODE -ne 0) {
    throw "WSL Ubuntu is missing Java and/or Python pip. Install prerequisites inside WSL, for example: sudo apt update && sudo apt install -y python3-pip python3-venv openjdk-17-jdk build-essential git zip unzip"
}

wsl.exe -d Ubuntu -- bash -lc "cd '$wslRepo' && python3 -m pip install --user --upgrade buildozer cython && export PATH=`$HOME/.local/bin:`$PATH && buildozer android debug"
if ($LASTEXITCODE -ne 0) {
    throw "Buildozer Android build failed with exit code $LASTEXITCODE"
}

$apk = Get-ChildItem -Path "bin" -Filter "*.apk" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($apk) {
    New-Item -ItemType Directory -Force -Path "dist" | Out-Null
    Copy-Item -LiteralPath $apk.FullName -Destination "dist\EchoText-Android-v0.1.0-debug.apk" -Force
}
