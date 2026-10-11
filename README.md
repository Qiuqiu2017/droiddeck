# DroidDeck

> 在 Linux 上像原生安卓一样安装并运行 Android 应用（APK）。

DroidDeck 是一个开源、跨平台的 **Android 应用运行器前端**。在 Linux 上，它通过
[Waydroid](https://waydroid.com/) 容器运行安卓系统，让你可以双击安装 APK、从应用库
启动应用，并像使用一台安卓平板一样操作它们。

它**不隐藏**自己的实现方式：主界面会明确告诉你「应用运行在 Android 容器中」。
运行应用时，你看到的就是真实的安卓界面——因为它们本来就是真实的安卓。

---

## 特性

- 现代、简洁的主界面
- 仿原生 Android 的 APK 安装界面（应用图标 / 名称 / 大小 / 安装进度）
- 已安装应用库，一键启动 / 卸载
- 一键打开 Android 桌面（全屏安卓体验）
- 透明的容器状态指示（运行中 / 已停止 / 未初始化）
- 后端抽象设计，便于扩展到其它平台
- 可选 Root 环境：启动时弹窗询问，默认启用；自动安装 Magisk 与 Shamiko 隐藏模块
- 防格机保护：Root 环境下拦截格式化分区、清空 /data、向块设备写入等危险操作
- 宿主机隔离：即使容器被格机，也无法触达宿主机磁盘（LXC 设备白名单）

## Root 环境

启动 DroidDeck 时会弹窗询问是否启用 Root 环境（默认勾选）。选择启用后：

- 安装 [Magisk](https://github.com/topjohnwu/Magisk)（Magisk Delta）为容器提供 root；
- 安装 [Shamiko](https://github.com/LSPosed/LSPosed.github.io) 隐藏模块；
- 开启 Zygisk 与 MagiskHide，用于对指定应用隐藏 root / 环境信息。

实现位于 `droiddeck/rootenv.py`（原生实现，运行时不依赖外部脚本）。


## 工作原理

```
DroidDeck (前端, PySide6)
        │  调用 CLI
        ▼
Waydroid  ──►  LXC 容器中的 LineageOS (Android 13)
        │
        ▼
   weston (嵌套 Wayland，供 X11 桌面出图)
```

DroidDeck 只是 Waydroid 的一个图形前端：它负责安装、枚举、启动应用，并在需要时
自动拉起一个嵌套的 Wayland 合成器（`weston`），让安卓界面显示在你的桌面上。

> **DroidDeck 不包含、也不分发任何 Android 系统镜像或第三方专有应用。**
> 你安装的应用是你自己提供并有权使用的 APK。

## 依赖

- Linux（X11 或 Wayland 桌面）
- [Waydroid](https://waydroid.com/) 及已初始化的安卓镜像
- `weston`（X11 桌面下用于嵌套 Wayland 合成器）
- Python ≥ 3.9 与 PySide6 ≥ 6.5

Debian 系 Linux：

```bash
sudo apt install waydroid weston python3-pyside6.qtwidgets
```

## 安装与运行

```bash
# 1. 初始化 Waydroid（首次使用，需要下载安卓镜像，约 1 GB）
sudo waydroid init

# 2. 运行 DroidDeck
pip install -e .
droiddeck            # 或： python -m droiddeck
```

## 打包

PyInstaller 不支持跨平台交叉编译，因此每个平台的包必须在各自系统上构建
（推荐用仓库自带的 GitHub Actions 自动完成，见下文）。

| 平台 | 运行 | 构建 |
| --- | --- | --- |
| Linux | `./run.sh` | `./build.sh`（另可 `./packaging/make_deb.sh` 生成 `.deb`）|
| macOS | `./run-macos.sh` | `./build-macos.sh` |
| Windows | `run.bat` | `build.bat` |

构建产物分别为 `dist/droiddeck-linux-*.tar.gz`、`dist/droiddeck-macos-*.tar.gz`、
`droiddeck-windows-x86_64.zip`。

> 说明：Windows / macOS 版本的界面可运行，但**尚无可用的 Android 运行后端**
> （运行应用依赖 Linux 上的 Waydroid），打开后会提示当前平台暂不支持运行。

## 开发

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e .
python -m droiddeck
```

## 许可证

GPL-3.0-or-later。详见 [LICENSE](LICENSE)。

DroidDeck 是一个独立项目，与 Waydroid、LineageOS、Android 及 Google 无隶属关系。
