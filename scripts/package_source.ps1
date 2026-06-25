$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path "dist" | Out-Null
$archive = "dist\EchoText-source-v0.1.0.zip"
if (Test-Path -LiteralPath $archive) {
    Remove-Item -LiteralPath $archive -Force
}

$stagingRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("EchoText-source-" + [System.Guid]::NewGuid().ToString("N"))

try {
    New-Item -ItemType Directory -Force -Path $stagingRoot | Out-Null

    $trackedFiles = git ls-files
    if ($LASTEXITCODE -ne 0) {
        throw "git ls-files failed with exit code $LASTEXITCODE"
    }

    foreach ($relativePath in $trackedFiles) {
        if (-not $relativePath) {
            continue
        }

        $sourcePath = Join-Path (Get-Location) $relativePath
        if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
            continue
        }

        $destinationPath = Join-Path $stagingRoot $relativePath
        $destinationDir = Split-Path -Parent $destinationPath
        if ($destinationDir) {
            New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null
        }

        Copy-Item -LiteralPath $sourcePath -Destination $destinationPath -Force
    }

    Compress-Archive -Path (Join-Path $stagingRoot "*") -DestinationPath $archive -Force
} finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
}
