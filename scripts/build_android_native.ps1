$ErrorActionPreference = "Stop"

function Resolve-AndroidSdkPath {
    if ($env:ANDROID_SDK_ROOT) {
        return $env:ANDROID_SDK_ROOT
    }
    if ($env:ANDROID_HOME) {
        return $env:ANDROID_HOME
    }

    $defaultSdk = Join-Path $env:LOCALAPPDATA "Android\Sdk"
    if (Test-Path -LiteralPath $defaultSdk) {
        return $defaultSdk
    }

    throw "ANDROID_SDK_ROOT was not set and no default Android SDK was found."
}

function Set-GradleProxyArgs {
    $proxy = $env:HTTPS_PROXY
    if (-not $proxy) {
        $proxy = $env:HTTP_PROXY
    }
    if (-not $proxy) {
        return
    }

    try {
        $uri = [System.Uri]$proxy
    } catch {
        Write-Warning "Unable to parse proxy URI '$proxy'. Continuing without explicit Gradle proxy JVM args."
        return
    }

    $props = @()
    if ($uri.Scheme -match "^https?$") {
        $props += "-Dhttp.proxyHost=$($uri.Host)"
        $props += "-Dhttp.proxyPort=$($uri.Port)"
        $props += "-Dhttps.proxyHost=$($uri.Host)"
        $props += "-Dhttps.proxyPort=$($uri.Port)"
    }
    if ($uri.UserInfo) {
        $parts = $uri.UserInfo.Split(":", 2)
        $props += "-Dhttp.proxyUser=$($parts[0])"
        $props += "-Dhttps.proxyUser=$($parts[0])"
        if ($parts.Length -gt 1) {
            $props += "-Dhttp.proxyPassword=$($parts[1])"
            $props += "-Dhttps.proxyPassword=$($parts[1])"
        }
    }

    if ($props.Count -gt 0) {
        $existing = $env:JAVA_TOOL_OPTIONS
        $env:JAVA_TOOL_OPTIONS = (($existing, ($props -join " ")) | Where-Object { $_ }) -join " "
    }
}

$sdkPath = Resolve-AndroidSdkPath
$androidProject = Join-Path (Get-Location) "android-app"
$localProperties = Join-Path $androidProject "local.properties"
$distDir = Join-Path (Get-Location) "dist"
$apkSource = Join-Path $androidProject "app\build\outputs\apk\debug\app-debug.apk"
$apkTarget = Join-Path $distDir "EchoText-Android-v0.1.0-debug.apk"

uv sync --group dev
uv run python scripts/generate_brand_assets.py
Set-GradleProxyArgs
New-Item -ItemType Directory -Force -Path $distDir | Out-Null
Set-Content -LiteralPath $localProperties -Value "sdk.dir=$($sdkPath -replace '\\','\\')" -Encoding ASCII

Push-Location $androidProject
try {
    .\gradlew.bat assembleDebug
    if ($LASTEXITCODE -ne 0) {
        throw "Gradle build failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $apkSource)) {
    throw "Expected APK was not produced at $apkSource"
}

Copy-Item -LiteralPath $apkSource -Destination $apkTarget -Force
Write-Host "Android APK copied to $apkTarget"
