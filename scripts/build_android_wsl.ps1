$ErrorActionPreference = "Stop"

$repo = (Resolve-Path ".").Path
$wslRepo = $repo -replace "^([A-Za-z]):", "/mnt/`$1" -replace "\\", "/"
$wslRepo = $wslRepo.ToLowerInvariant()

wsl.exe -d Ubuntu -- bash -lc "command -v java >/dev/null && command -v ant >/dev/null && python3 -m pip --version >/dev/null"
if ($LASTEXITCODE -ne 0) {
    throw "WSL Ubuntu is missing Java, Ant, and/or Python pip. Install prerequisites inside WSL, for example: sudo apt update && sudo apt install -y python3-pip python3-venv openjdk-17-jdk ant build-essential git zip unzip"
}

wsl.exe -d Ubuntu -- bash -lc "cd '$wslRepo' && export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin && mkdir -p `$HOME/.buildozer/android/platform/apache-ant-1.9.4/bin && ln -sf `$(command -v ant) `$HOME/.buildozer/android/platform/apache-ant-1.9.4/bin/ant && python3 -m venv .buildozer-venv && . .buildozer-venv/bin/activate && python -m pip install --upgrade pip buildozer cython==0.29.37 && buildozer android debug"
if ($LASTEXITCODE -ne 0) {
    throw "Buildozer Android build failed with exit code $LASTEXITCODE"
}

$apk = Get-ChildItem -Path "bin" -Filter "*.apk" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($apk) {
    New-Item -ItemType Directory -Force -Path "dist" | Out-Null
    Copy-Item -LiteralPath $apk.FullName -Destination "dist\EchoText-Android-v0.1.0-debug.apk" -Force
}
