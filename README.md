# EchoText

<p align="center">
  <img src="./assets/branding/echotext-icon-256.png" width="112" alt="EchoText icon" />
</p>

<p align="center">
  同一局域网内，在 Windows 和 Android 之间快速配对、双向传输文本。
</p>

<p align="center">
  <a href="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white"><img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python 3.12" /></a>
  <a href="https://img.shields.io/badge/Android-API%2024%2B-34A853?logo=android&logoColor=white"><img src="https://img.shields.io/badge/Android-API%2024%2B-34A853?logo=android&logoColor=white" alt="Android API 24+" /></a>
  <a href="https://img.shields.io/badge/Platform-Windows%20%2B%20Android-0A84FF"><img src="https://img.shields.io/badge/Platform-Windows%20%2B%20Android-0A84FF" alt="Windows and Android" /></a>
  <a href="https://img.shields.io/badge/Dependencies-uv-7C3AED"><img src="https://img.shields.io/badge/Dependencies-uv-7C3AED" alt="uv managed" /></a>
  <a href="https://img.shields.io/badge/Lint-ruff-F1B722"><img src="https://img.shields.io/badge/Lint-ruff-F1B722" alt="ruff" /></a>
</p>

<!-- README-I18N:START -->

**简体中文** | [English](./README.en.md)

<!-- README-I18N:END -->

> [!NOTE]
> EchoText 面向受信任的本地网络，例如家庭 Wi-Fi、办公室局域网或热点共享网络。它不是端到端加密的互联网聊天工具。

## 概览

- Windows 桌面端：Python 3.12 + Kivy
- Android 端：原生 Java + Android SDK
- 发现机制：UDP 广播，端口 `48734`
- 传输机制：HTTP `POST /api/v1/pair` 与 `POST /api/v1/messages`
- 完整性校验：基于已配对设备的 HMAC-SHA256 签名
- 剪贴板：支持手动粘贴、发送、复制最新文本和前台自动同步
- 历史记录：默认仅保留会话内历史，可选本地持久化
- 图标与打包：统一品牌图标同时用于 Android 启动图标、Windows EXE、窗口图标和安装器
- 应用语言：桌面端与 Android 端均固定为简体中文界面，不提供语言切换入口

当前 Android 交付物来自 [`android-app/`](/C:/Users/SoloEternity/Documents/Code/EchoText/android-app) 原生工程。旧的 Buildozer 路线仅保留为历史上下文，不再作为推荐 APK 交付方式。

## 安装

使用 `dist/` 目录中的构建产物：

- Android：`EchoText-Android-v0.1.0-debug.apk`
- Windows：`EchoText-Setup-v0.1.0.exe`
- 源码压缩包：`EchoText-source-v0.1.0.zip`

请确保手机和电脑连接在同一局域网。Windows 安装器会为 `EchoText.exe` 自动添加 `LocalSubnet` 入站规则，并覆盖 Private 与 Public 网络；如果你从源码运行，首次弹出防火墙提示时仍需允许本地网络访问。

如果设备刚从宿舍 Wi-Fi、手机热点、校园网之间切换过，请把两端应用都重新打开一次。最新版本会同时广播多个候选局域网地址，并在配对/发送时自动回退尝试这些地址。

## 配对与发送

1. 在手机和电脑上都打开 EchoText。
2. 等待目标设备出现在设备列表中。
3. 查看目标设备显示的 6 位配对码。
4. 在另一台设备输入配对码并点击 `配对`。
5. 粘贴或输入文本后点击 `发送`。
6. 收到的文本会自动写入历史记录区，并可一键复制最新内容。

前台自动同步只会在应用保持前台打开时同步剪贴板变化。当前应用界面固定使用简体中文显示。

## 开发

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

从源码运行 Windows 桌面端：

```powershell
uv run echotext
```

> [!TIP]
> 当前仓库没有 `.github` workflow，因此 badge 只展示静态技术信息，不展示 CI 状态。

## 构建

生成品牌资产：

```powershell
uv run python scripts/generate_brand_assets.py
```

创建源码压缩包：

```powershell
.\scripts\package_source.ps1
```

构建 Windows 应用与安装器：

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

## 打包产物

构建成功后，`dist/` 中会生成：

- `EchoText-source-v0.1.0.zip`
- `EchoText-Android-v0.1.0-debug.apk`
- `EchoText-Setup-v0.1.0.exe`

## 常见问题

- `python` 打开 Microsoft Store 或命中坏掉的 shim：
  运行 `.\scripts\repair_toolchain.ps1`。
- `pip` 不在 `PATH`：
  重新安装或重置 Scoop Python，然后重开 PowerShell。
- `uv run` 用了错误的解释器：
  确认 `.python-version` 为 `3.12`，然后执行 `uv sync --group dev`。
- Android 构建找不到 SDK：
  设置 `ANDROID_SDK_ROOT`，或把 SDK 安装到 `%LOCALAPPDATA%\Android\Sdk`。
- 设备互相发现不到：
  确认两台设备在同一 Wi-Fi，且网络没有屏蔽本地广播。升级后请把两端都重新打开一次，新版本会同时向 `255.255.255.255`、多个本地子网广播地址发送发现包，并在历史地址之间自动回退。
- 校园网下发现不到设备：
  很多校园网会把同一 SSID 下的终端拆到不同子网，或者直接开启 client isolation / AP isolation，导致广播发现和终端互访都被限制。这种情况下不是 EchoText 单独能完全绕过去的问题。新版本已经补上多地址广播和历史地址回退；如果依然互相看不到，通常只能改用宿舍局域网、手机热点，或联系网络管理员确认是否允许终端互访。
- 配对失败：
  重新读取目标设备的 6 位配对码；配对码 5 分钟后会过期。如果设备刚换过网络，先刷新设备列表或重开应用，让最新地址重新广播出来。如果 Windows 端来自源码运行，还要确认 Windows Defender 防火墙已经允许当前进程访问本地子网。
- Android 能接收 Windows 消息，但无法回发：
  这通常是旧网络地址缓存或多网卡选路导致。升级两端到最新构建后，各自重新打开一次应用；新版本会保存并轮流尝试多个候选地址。必要时重新配对一次，把旧热点/旧 Wi-Fi 的地址缓存刷掉。
- Windows 桌面端中文仍显示异常：
  安装微软雅黑、等线、黑体或 Noto Sans SC 等常见中文系统字体后重新启动 EchoText。
