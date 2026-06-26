$ErrorActionPreference = "Stop"

.\scripts\test.ps1
.\scripts\package_source.ps1
.\scripts\build_windows.ps1
.\scripts\build_android_native.ps1
