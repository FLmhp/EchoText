[app]
title = EchoText
package.name = echotext
package.domain = org.echotext
source.dir = .
source.include_exts = py,kv,png,jpg,json,toml,md
source.exclude_dirs = .git,.venv,.buildozer,.buildozer-cache,.buildozer-venv,.pytest_cache,.ruff_cache,bin,build,dist,tests
version = 0.1.0
requirements = python3==3.12.13,hostpython3==3.12.13,kivy
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,CHANGE_WIFI_MULTICAST_STATE
android.api = 35
android.minapi = 24
android.archs = arm64-v8a,armeabi-v7a
android.accept_sdk_license = True
log_level = 2
warn_on_root = 1

[buildozer]
log_level = 2
warn_on_root = 1
