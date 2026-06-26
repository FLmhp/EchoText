# EchoText

[English](#english) | [中文](#中文)

EchoText is a small LAN text bridge for Android and Windows. It lets nearby devices discover each other, pair with a six digit code, send text, copy received text, and optionally sync clipboard changes while the app is open.

> [!NOTE]
> EchoText is designed for trusted local networks such as a home Wi-Fi or office LAN. Pairing prevents casual unsolicited messages, but v0.1.0 is not an end-to-end encrypted public-network messenger.

## English

### Features

- Android and Windows support from one Python/Kivy codebase.
- UDP LAN discovery and HTTP text transfer.
- Six digit pairing code with per-peer HMAC message signatures.
- Manual paste/send/copy workflow.
- Optional foreground clipboard auto sync.
- Session-only history by default, with optional local persistent history.
- Chinese and English UI.

### Install

Use the packaged installers from `dist/`:

- Android: install `EchoText-Android-v0.1.0-debug.apk`.
- Windows: run `EchoText-Setup-v0.1.0.exe`.

Both devices must be on the same LAN. Allow local network/firewall prompts for EchoText on Windows and network access on Android.

### Use

1. Open EchoText on both devices.
2. Wait for the target device to appear in the device list.
3. Read the target device's visible pair code.
4. Enter that code on the sending device and press `Pair`.
5. Paste or type text, then press `Send`.
6. Received text is copied to the local clipboard automatically and appears in the history panel.

Foreground auto sync sends clipboard changes only while EchoText is open. This keeps Android permissions and background behavior predictable.

On Android, EchoText stores settings and optional history in the app's private internal storage so startup does not depend on writable shared storage paths.

### Development

EchoText uses Python 3.12 through `uv` for project dependency management. A global `python` and `pip` should still be available on `PATH` for compatibility and diagnostics, but project dependencies should be installed with `uv`.

Repair or verify the Windows toolchain:

```powershell
.\scripts\repair_toolchain.ps1
```

Install project dependencies and run checks:

```powershell
uv sync --group dev
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

Run the app from source:

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

If `ISCC.exe` is missing, install Inno Setup:

```powershell
winget install --id JRSoftware.InnoSetup -e
```

Build the Android APK through WSL/Ubuntu:

```powershell
.\scripts\build_android_wsl.ps1
```

The WSL environment needs `python3`, `pip`, Java, Buildozer, and the Android SDK/NDK toolchain. Buildozer downloads most Android components during the first build. The current Android package targets API 35 with a minimum supported Android API level of 24, and the Android packaging toolchain is pinned to `python3==3.12.13` with `hostpython3==3.12.13` for compatibility with the current `python-for-android` release.

On Ubuntu, install the required base packages before running the Android build:

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv openjdk-17-jdk ant autoconf automake libtool pkg-config dos2unix build-essential git zip unzip libssl-dev libffi-dev libsqlite3-dev libbz2-dev libreadline-dev libncurses-dev libgdbm-dev tk-dev uuid-dev liblzma-dev
```

If you use a local Windows proxy such as `http://127.0.0.1:7897`, keep `HTTPS_PROXY` or `HTTP_PROXY` set in PowerShell before launching `.\scripts\build_android_wsl.ps1`. The script rewrites `localhost` to the WSL-reachable Windows host address automatically, and it forwards the same proxy settings to Gradle/Java so Android build downloads can reach Google's Maven repositories from WSL.

### Troubleshooting

- `python` opens Microsoft Store: remove stale shims and run `.\scripts\repair_toolchain.ps1`.
- `pip` is not found: reinstall or reset Scoop Python, then reopen PowerShell.
- Devices do not appear: confirm both devices are on the same Wi-Fi, firewall allows EchoText, and multicast/broadcast traffic is not blocked.
- Pairing fails: rotate or re-read the target device's six digit code; codes expire after five minutes.
- Android clipboard sync seems limited: automatic sync is intentionally foreground-only.
- Android stays on the loading page or closes right after launch: rebuild and reinstall the latest APK. v0.1.0 now delays clipboard initialization until the UI is ready and stores settings in Android app-private storage to avoid early startup crashes.
- WSL reports that localhost proxy settings are not mirrored: keep the Windows-side proxy env vars set and run `.\scripts\build_android_wsl.ps1`; it rewrites `127.0.0.1` or `localhost` to the WSL NAT gateway automatically.
- Buildozer stops at `autoreconf: not found`: install `autoconf automake libtool pkg-config` inside WSL, then rerun the Android build script.
- Buildozer fails at `gradlew` with `/usr/bin/env: 'bash\\r'`: install `dos2unix` inside WSL and rerun `.\scripts\build_android_wsl.ps1`; `python-for-android` will normalize `gradlew` automatically once the tool is present.
- Buildozer reaches the hostpython `pip` step and reports that the SSL module is not available: keep `requirements = python3==3.12.13,hostpython3==3.12.13,kivy` in `buildozer.spec`; the current `python-for-android` default CPython 3.14.2 path can fail there.
- Buildozer reaches the hostpython `pip` step and reports that the SSL module is not available even on Python 3.12: install the WSL development packages listed above, especially `libssl-dev`, then clean the Android build directory and rerun the script.
- Buildozer reaches the pure Python module install stage and `pip` fails with `RequirementInformation`: rerun `.\scripts\build_android_wsl.ps1`; it patches the current `python-for-android` venv bootstrap for Debian/Ubuntu's mixed `resolvelib` vendor layout before package installation starts.

## 中文

### 功能

- 一套 Python/Kivy 代码同时支持 Android 和 Windows。
- 使用 UDP 在局域网发现设备，使用 HTTP 传输文本。
- 通过 6 位配对码建立设备关系，并使用 HMAC 校验消息。
- 支持手动粘贴、发送、复制。
- 支持前台运行时自动同步剪贴板。
- 默认只保存会话内历史，可在设置中开启本地持久历史。
- 应用界面支持中文和 English。

### 安装

使用 `dist/` 目录中的安装包：

- Android：安装 `EchoText-Android-v0.1.0-debug.apk`。
- Windows：运行 `EchoText-Setup-v0.1.0.exe`。

两台设备必须连接到同一个局域网。Windows 上请允许 EchoText 通过防火墙，Android 上请允许网络访问。

### 使用

1. 在两台设备上打开 EchoText。
2. 等待目标设备出现在设备列表中。
3. 查看目标设备界面上显示的配对码。
4. 在发送设备中输入该配对码并点击 `配对`。
5. 粘贴或输入文本，然后点击 `发送`。
6. 收到的文本会自动复制到本机剪贴板，并显示在历史区域。

前台自动同步只在 EchoText 打开时发送剪贴板变化，这样可以减少 Android 后台权限和系统限制带来的不确定性。

在 Android 上，EchoText 会把设置和可选历史记录写入应用私有内部存储，避免启动阶段依赖可写的共享存储路径。

### 开发

EchoText 通过 `uv` 使用 Python 3.12 管理项目依赖。全局 `python` 和 `pip` 仍需要出现在 `PATH` 中，方便兼容脚本和诊断；但项目依赖请统一使用 `uv` 安装和运行。

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

从源码运行：

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

如果缺少 `ISCC.exe`，安装 Inno Setup：

```powershell
winget install --id JRSoftware.InnoSetup -e
```

通过 WSL/Ubuntu 构建 Android APK：

```powershell
.\scripts\build_android_wsl.ps1
```

WSL 环境需要 `python3`、`pip`、Java、Buildozer 和 Android SDK/NDK 工具链。第一次构建时 Buildozer 会下载多数 Android 组件。当前 Android 安装包以 API 35 为目标，最低支持 Android API 24，并且 Android 打包链固定使用 `python3==3.12.13` 与 `hostpython3==3.12.13`，以兼容当前 `python-for-android` 版本。

Ubuntu 中请先安装基础依赖：

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv openjdk-17-jdk ant autoconf automake libtool pkg-config dos2unix build-essential git zip unzip libssl-dev libffi-dev libsqlite3-dev libbz2-dev libreadline-dev libncurses-dev libgdbm-dev tk-dev uuid-dev liblzma-dev
```

如果你在 Windows 上使用 `http://127.0.0.1:7897` 这类本地代理，请在 PowerShell 中先设置好 `HTTPS_PROXY` 或 `HTTP_PROXY`，再执行 `.\scripts\build_android_wsl.ps1`。脚本会自动把 `localhost` 改写成 WSL 可访问的 Windows 主机地址，并把同一套代理参数传给 Gradle/Java，避免 NAT 模式下 “WSL 不支持 localhost 代理” 以及 Android 构建下载依赖超时的常见问题。

### 故障排查

- `python` 打开 Microsoft Store：移除残留 shim，并运行 `.\scripts\repair_toolchain.ps1`。
- 找不到 `pip`：重新安装或重置 Scoop Python，然后重新打开 PowerShell。
- 设备没有出现：确认两台设备在同一 Wi-Fi、Windows 防火墙允许 EchoText、网络未屏蔽广播/组播。
- 配对失败：重新查看或刷新目标设备上的 6 位配对码；配对码 5 分钟后过期。
- Android 剪贴板自动同步受限：自动同步按设计仅支持应用前台运行时工作。
- Android 安装后卡在 loading 页面或启动即退出：请重新构建并安装最新 APK。v0.1.0 现已把剪贴板初始化延后到界面就绪之后，并把设置目录切换到 Android 应用私有存储，以规避启动早期崩溃。
- WSL 提示 localhost 代理没有镜像：保持 Windows 侧代理环境变量已设置，然后运行 `.\scripts\build_android_wsl.ps1`；脚本会自动把 `127.0.0.1` 或 `localhost` 改写为 WSL NAT 网关地址。
- Buildozer 卡在 `autoreconf: not found`：在 WSL 里安装 `autoconf automake libtool pkg-config`，然后重新执行 Android 构建脚本。
- Buildozer 在 `gradlew` 阶段报 `/usr/bin/env: 'bash\r'`：在 WSL 中安装 `dos2unix`，然后重跑 `.\scripts\build_android_wsl.ps1`；`python-for-android` 检测到该工具后会自动把 `gradlew` 转成 Unix 行尾。
- Buildozer 进行到 hostpython 的 `pip` 阶段并提示 SSL 模块不可用：请把 `buildozer.spec` 里的 `requirements` 保持为 `python3==3.12.13,hostpython3==3.12.13,kivy`；当前 `python-for-android` 默认的 CPython 3.14.2 链路可能会在这里失败。
- 即使已经切到 Python 3.12，Buildozer 在 hostpython 的 `pip` 阶段仍提示 SSL 模块不可用：请先安装上面列出的 WSL 开发包，尤其是 `libssl-dev`，然后清理 Android 构建目录并重新执行脚本。
- Buildozer 已进入纯 Python 模块安装阶段，但 `pip` 报 `RequirementInformation` 错误：直接重跑 `.\scripts\build_android_wsl.ps1`；脚本会在安装开始前修补当前 `python-for-android` 的 venv 引导逻辑，以兼容 Debian/Ubuntu 下混合的 `resolvelib` vendor 布局。
