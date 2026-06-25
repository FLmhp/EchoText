$ErrorActionPreference = "Stop"

function Convert-ProxyForWsl {
    param(
        [string]$ProxyUri,
        [string]$WslHostAddress
    )

    if ([string]::IsNullOrWhiteSpace($ProxyUri)) {
        return $null
    }

    $uri = [Uri]$ProxyUri
    if ($uri.Host -in @("127.0.0.1", "localhost", "::1")) {
        $builder = [UriBuilder]$uri
        $builder.Host = $WslHostAddress
        return $builder.ToString().TrimEnd("/")
    }

    return $ProxyUri.TrimEnd("/")
}

$repo = (Resolve-Path ".").Path
$wslRepo = $repo -replace "^([A-Za-z]):", "/mnt/`$1" -replace "\\", "/"
$wslRepo = $wslRepo.ToLowerInvariant()

$wslGateway = (wsl.exe -d Ubuntu -- bash -lc 'ip route show default | cut -d" " -f3 | head -1').Trim()
if (-not $wslGateway) {
    $wslGateway = (wsl.exe -d Ubuntu -- bash -lc 'grep -m1 "^nameserver " /etc/resolv.conf | cut -d" " -f2').Trim()
}
if (-not $wslGateway) {
    throw "Unable to determine a WSL-reachable host address for proxy rewriting."
}

$rawHttpsProxy = if ($env:HTTPS_PROXY) { $env:HTTPS_PROXY } elseif ($env:https_proxy) { $env:https_proxy } else { "http://127.0.0.1:7897" }
$rawHttpProxy = if ($env:HTTP_PROXY) { $env:HTTP_PROXY } elseif ($env:http_proxy) { $env:http_proxy } else { $rawHttpsProxy }
$rawAllProxy = if ($env:ALL_PROXY) { $env:ALL_PROXY } elseif ($env:all_proxy) { $env:all_proxy } else { $rawHttpsProxy }

$wslHttpsProxy = Convert-ProxyForWsl -ProxyUri $rawHttpsProxy -WslHostAddress $wslGateway
$wslHttpProxy = Convert-ProxyForWsl -ProxyUri $rawHttpProxy -WslHostAddress $wslGateway
$wslAllProxy = Convert-ProxyForWsl -ProxyUri $rawAllProxy -WslHostAddress $wslGateway

$proxyExports = @"
export HTTP_PROXY='$wslHttpProxy'
export HTTPS_PROXY='$wslHttpsProxy'
export ALL_PROXY='$wslAllProxy'
export http_proxy='$wslHttpProxy'
export https_proxy='$wslHttpsProxy'
export all_proxy='$wslAllProxy'
export NO_PROXY='localhost,127.0.0.1,::1'
export no_proxy='localhost,127.0.0.1,::1'
"@

wsl.exe -d Ubuntu -- bash -lc "command -v java >/dev/null && command -v ant >/dev/null && python3 -m pip --version >/dev/null"
if ($LASTEXITCODE -ne 0) {
    throw "WSL Ubuntu is missing Java, Ant, and/or Python pip. Install prerequisites inside WSL, for example: sudo apt update && sudo apt install -y python3-pip python3-venv openjdk-17-jdk ant build-essential git zip unzip"
}

$wslBuildCommand = @'
set -euo pipefail
cd '__WSL_REPO__'
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
__PROXY_EXPORTS__

mkdir -p "$HOME/.buildozer/android/platform/apache-ant-1.9.4/bin"
ln -sf "$(command -v ant)" "$HOME/.buildozer/android/platform/apache-ant-1.9.4/bin/ant"

python_archive_source=""
for candidate in /home/ubuntu/v3.14.2.tar.gz /home/ubuntu/python-3.14.2.tar.gz; do
  if [ -f "$candidate" ]; then
    python_archive_source="$candidate"
    break
  fi
done

if [ -n "$python_archive_source" ]; then
  for recipe_name in hostpython3 python3; do
    recipe_dir="$PWD/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/packages/$recipe_name"
    mkdir -p "$recipe_dir"
    cp -f "$python_archive_source" "$recipe_dir/v3.14.2.tar.gz"
    touch "$recipe_dir/.mark-v3.14.2.tar.gz"
  done
fi

python3 -m venv .buildozer-venv
. .buildozer-venv/bin/activate
python -m pip install --upgrade pip buildozer cython==0.29.37
buildozer android debug
'@
$wslBuildCommand = $wslBuildCommand.Replace("__WSL_REPO__", $wslRepo).Replace("__PROXY_EXPORTS__", $proxyExports.Trim())

wsl.exe -d Ubuntu -- bash -lc $wslBuildCommand
if ($LASTEXITCODE -ne 0) {
    throw "Buildozer Android build failed with exit code $LASTEXITCODE"
}

$apk = Get-ChildItem -Path "bin" -Filter "*.apk" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($apk) {
    New-Item -ItemType Directory -Force -Path "dist" | Out-Null
    Copy-Item -LiteralPath $apk.FullName -Destination "dist\EchoText-Android-v0.1.0-debug.apk" -Force
}
