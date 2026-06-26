# EchoText

[English](#english) | [中文](#中文)

EchoText is a LAN text bridge between Windows and Android. It discovers nearby devices on the same network, pairs them with a six digit code, transfers text over HTTP with HMAC verification, and keeps the workflow close to copy/paste.

> [!NOTE]
> EchoText is meant for trusted local networks such as home Wi-Fi or office LANs. It is not an end-to-end encrypted internet messenger.

## English

### Overview

- Windows desktop app: Python 3.12 + Kivy
- Android app: native Java + Android SDK
- Discovery: UDP broadcast on port `48734`
- Transport: HTTP `POST /api/v1/pair` and `POST /api/v1/messages`
- Integrity: per-peer HMAC-SHA256 signatures
- Clipboard: manual paste/send/copy plus optional foreground auto sync
- History: session-only by default, optional local persistence
- UI: English and Chinese, Android defaults to system language and supports manual switching
- Desktop language: Windows now defaults to Chinese on first launch, supports manual switching, and automatically uses a local CJK system font when available

The current Android deliverable is the native Java app under [`android-app/`](/C:/Users/SoloEternity/Documents/Code/EchoText/android-app). The older `python-for-android` / Buildozer path is kept only as legacy build context and is no longer the recommended route for APK delivery.

### Install

Use the packaged artifacts from `dist/`:

- Android: `EchoText-Android-v0.1.0-debug.apk`
- Windows: `EchoText-Setup-v0.1.0.exe`
- Source: `EchoText-source-v0.1.0.zip`

Keep both devices on the same LAN. The Windows installer now adds a `LocalSubnet` firewall rule for `EchoText.exe` on both Private and Public networks; if you run from source, still allow Windows firewall access when prompted.

### Use

1. Open EchoText on both devices.
2. Wait for the target device to appear in the device list.
3. Read the target device's visible pair code.
4. Enter that code on the other device and press `Pair`.
5. Paste or type text, then press `Send`.
6. Received text is copied locally and appended to the history panel.

Foreground auto sync only mirrors clipboard changes while the app stays open in the foreground.

### Development

EchoText uses `uv` for project dependency management. A global `python` and `pip` should still exist on `PATH` for compatibility and diagnostics, but project dependencies should be managed with `uv`.

Repair or verify the Windows toolchain:

```powershell
.\scripts\repair_toolchain.ps1
```

Install dependencies and run checks:

```powershell
uv sync --group dev
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

Run the Windows app from source:

```powershell
uv run echotext
```

### Build

Create the source archive:

```powershell
.\scripts\package_source.ps1
```

Build the Windows app and installer:

```powershell
.\scripts\build_windows.ps1
```

Build the Android APK on Windows with the local Android SDK:

```powershell
.\scripts\build_android_native.ps1
```

Run the full build flow:

```powershell
.\scripts\build_all.ps1
```

The Android build expects one of these:

- `ANDROID_SDK_ROOT`
- `ANDROID_HOME`
- default SDK path at `%LOCALAPPDATA%\Android\Sdk`

If you use an HTTP/HTTPS proxy, keep `HTTP_PROXY` or `HTTPS_PROXY` set before launching the Android build. The script forwards those settings to Gradle's JVM arguments.

### Packaging Outputs

Successful builds place these files in `dist/`:

- `EchoText-source-v0.1.0.zip`
- `EchoText-Android-v0.1.0-debug.apk`
- `EchoText-Setup-v0.1.0.exe`

### Validation

Completed validation for the current Android app includes:

- native Java APK builds successfully with Gradle
- APK installs on a real HarmonyOS 4.2 / Android 12 compatible device through `adb shell pm install`
- app launches on device without the previous loading-screen crash
- Android no longer fails with `Cleartext HTTP traffic ... not permitted` when talking to LAN peers
- Windows desktop Chinese UI no longer depends on the Kivy default font and uses a compatible local system font
- Windows-to-Android pairing and signed message delivery works with English, Chinese, and multiline text

### Troubleshooting

- `python` opens the Microsoft Store or points to a dead shim:
  Run `.\scripts\repair_toolchain.ps1`.
- `pip` is missing from `PATH`:
  Reinstall or reset Scoop Python, then reopen PowerShell.
- `uv run` uses the wrong interpreter:
  Confirm `.python-version` is `3.12` and run `uv sync --group dev`.
- Android build cannot find the SDK:
  Set `ANDROID_SDK_ROOT` or install the SDK to `%LOCALAPPDATA%\Android\Sdk`.
- `adb install` is rejected on HarmonyOS:
  Use `adb push ... /data/local/tmp/...` followed by `adb shell pm install -r -t ...`, or enable the device's USB install permission flow.
- Devices do not appear:
    Make sure both devices are on the same Wi-Fi and local broadcast traffic is not blocked.
- Pairing fails:
    Re-read the target pair code; codes expire after five minutes. If the Windows app is launched from source or an older installer, also confirm Windows Defender Firewall allows `EchoText.exe` or `python.exe` for local subnet access.
- Windows Chinese text still renders incorrectly:
    Install a standard Chinese system font such as Microsoft YaHei, DengXian, SimHei, or Noto Sans SC, then restart EchoText.

## 中文

### 概览

- Windows 桌面端：Python 3.12 + Kivy
- Android 端：原生 Java + Android SDK
- 发现机制：UDP 广播，端口 `48734`
- 传输机制：HTTP `POST /api/v1/pair` 与 `POST /api/v1/messages`
- 完整性校验：基于每个已配对设备的 HMAC-SHA256 签名
- 剪贴板：支持手动粘贴/发送/复制，也支持前台自动同步
- 历史记录：默认只保留会话内历史，可选本地持久化
- 界面语言：支持中英双语，Android 默认跟随系统语言，也可手动切换
- 桌面端语言：Windows 首次启动默认中文，也支持手动切换，并会优先使用本机可用的中文系统字体

当前可交付的 Android 方案是原生 Java 工程 [`android-app/`](/C:/Users/SoloEternity/Documents/Code/EchoText/android-app)。旧的 `python-for-android` / Buildozer 路线仅作为历史构建上下文保留，不再是推荐的 APK 交付方式。

### 安装

使用 `dist/` 目录中的构建产物：

- Android：`EchoText-Android-v0.1.0-debug.apk`
- Windows：`EchoText-Setup-v0.1.0.exe`
- 源码压缩包：`EchoText-source-v0.1.0.zip`

请确保手机和电脑连接在同一个局域网内。Windows 安装器现在会为 `EchoText.exe` 自动添加 `LocalSubnet` 入站规则，并同时覆盖 Private 与 Public 网络；如果你是从源码运行，首次弹出防火墙提示时仍需允许 EchoText 访问本地网络。

### 使用

1. 在两台设备上打开 EchoText。
2. 等待目标设备出现在设备列表中。
3. 查看目标设备界面显示的 6 位配对码。
4. 在另一台设备输入该配对码并点击 `配对`。
5. 粘贴或输入文本，然后点击 `发送`。
6. 收到的文本会复制到本地，并写入历史记录区域。

前台自动同步只会在应用保持前台打开时同步剪贴板变化。

### 开发

EchoText 使用 `uv` 管理项目依赖。全局 `python` 和 `pip` 仍需要出现在 `PATH` 中，方便兼容脚本和诊断，但项目依赖请统一通过 `uv` 管理。

修复或验证 Windows 工具链：

```powershell
.\scripts\repair_toolchain.ps1
```

安装依赖并运行检查：

```powershell
uv sync --group dev
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

从源码运行 Windows 端：

```powershell
uv run echotext
```

### 构建

创建源码压缩包：

```powershell
.\scripts\package_source.ps1
```

构建 Windows 应用和安装器：

```powershell
.\scripts\build_windows.ps1
```

使用本机 Android SDK 构建原生 Java APK：

```powershell
.\scripts\build_android_native.ps1
```

执行完整构建流程：

```powershell
.\scripts\build_all.ps1
```

Android 构建脚本会按以下顺序查找 SDK：

- `ANDROID_SDK_ROOT`
- `ANDROID_HOME`
- 默认路径 `%LOCALAPPDATA%\Android\Sdk`

如果需要代理，请在运行 Android 构建脚本前设置 `HTTP_PROXY` 或 `HTTPS_PROXY`。脚本会把代理参数传给 Gradle。

### 交付产物

构建成功后，`dist/` 中会生成：

- `EchoText-source-v0.1.0.zip`
- `EchoText-Android-v0.1.0-debug.apk`
- `EchoText-Setup-v0.1.0.exe`

### 验证情况

当前 Android 方案已经完成这些验证：

- 原生 Java APK 可通过 Gradle 成功构建
- APK 可通过 `adb shell pm install` 安装到 HarmonyOS 4.2 / Android 12 兼容设备
- 应用可在真机正常启动，不再出现之前的 loading 卡死和闪退
- Android 访问局域网设备时不再触发 `Cleartext HTTP traffic ... not permitted`
- Windows 桌面端中文界面不再依赖 Kivy 默认字体，可自动选择兼容的本机系统字体
- Windows 到 Android 的配对与签名消息传输可正常工作，已验证英文、中文和多行文本

### 故障排查

- `python` 打开 Microsoft Store 或命中坏掉的 shim：
  运行 `.\scripts\repair_toolchain.ps1`。
- `pip` 不在 `PATH`：
  重新安装或重置 Scoop Python，然后重开 PowerShell。
- `uv run` 用了错误的解释器：
  确认 `.python-version` 为 `3.12`，然后执行 `uv sync --group dev`。
- Android 构建找不到 SDK：
  设置 `ANDROID_SDK_ROOT`，或把 SDK 安装到 `%LOCALAPPDATA%\Android\Sdk`。
- HarmonyOS 下 `adb install` 被系统拦截：
    改用 `adb push ... /data/local/tmp/...` 再执行 `adb shell pm install -r -t ...`，或者在手机开发者选项中放行 USB 安装。
- 设备互相发现不到：
    确认两台设备在同一 Wi-Fi，且网络没有屏蔽本地广播。
- 配对失败：
    重新读取目标设备的 6 位配对码；配对码 5 分钟后会过期。如果 Windows 端来自源码运行或旧版安装包，还要确认 Windows Defender 防火墙已经允许 `EchoText.exe` 或 `python.exe` 访问本地子网。
- Windows 桌面端中文仍显示异常：
    安装微软雅黑、等线、黑体或 Noto Sans SC 等常见中文系统字体后重新启动 EchoText。
