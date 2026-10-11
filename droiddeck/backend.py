"""Runtime backends for DroidDeck.

The Linux backend drives the Waydroid Android container through its CLI.
All potentially blocking calls take a timeout and the compositor/session are
managed so a dead Wayland compositor never freezes the UI again.
"""

from __future__ import annotations

import os
import re
import signal
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


class BackendError(RuntimeError):
    """Raised when a backend operation fails."""


@dataclass
class ContainerState:
    session: str = "STOPPED"      # STOPPED / RUNNING / STARTING
    container: str = "STOPPED"
    initialized: bool = False
    android_version: str = ""
    runtime_label: str = ""


@dataclass
class AndroidApp:
    package: str
    name: str
    icon_path: Optional[str] = None
    system: bool = False
    running: bool = False


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------
class AndroidBackend:
    """Common interface every platform backend must implement."""

    runtime_name = "Android 运行时"

    def state(self) -> ContainerState:
        raise NotImplementedError

    def start_session(self, on_line: Callable[[str], None] | None = None) -> None:
        raise NotImplementedError

    def list_apps(self) -> list[AndroidApp]:
        raise NotImplementedError

    def install_apk(self, apk: str, on_line: Callable[[str], None] | None = None) -> None:
        raise NotImplementedError

    def remove_app(self, package: str) -> None:
        raise NotImplementedError

    def launch_app(self, package: str) -> None:
        raise NotImplementedError

    def show_full_ui(self) -> None:
        raise NotImplementedError


def _proc_running(name: str) -> bool:
    """True if ANY process with this comm name is alive (non-zombie)."""
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/comm") as fh:
                if fh.read().strip() != name:
                    continue
            with open(f"/proc/{pid}/stat") as fh:
                data = fh.read()
            state = data[data.rfind(")") + 2]
        except OSError:
            continue
        if state != "Z":
            return True
    return False


# ---------------------------------------------------------------------------
# Waydroid backend (Linux)
# ---------------------------------------------------------------------------
class WaydroidBackend(AndroidBackend):
    runtime_name = "Waydroid 容器"
    COMPOSITOR_SOCKET = "wayland-droiddeck"

    def __init__(self) -> None:
        self._weston: subprocess.Popen | None = None
        self._session_proc: subprocess.Popen | None = None

    # -- low level ---------------------------------------------------------
    def is_installed(self) -> bool:
        return shutil.which("waydroid") is not None

    def _runtime_dir(self) -> Path:
        return Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))

    def _env(self) -> dict:
        env = os.environ.copy()
        env["XDG_RUNTIME_DIR"] = str(self._runtime_dir())
        return env

    def _run(self, args: list[str], timeout: float = 20) -> str:
        try:
            p = subprocess.run(
                args, capture_output=True, text=True,
                env=self._env(), timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return ""
        except OSError:
            return ""
        return p.stdout or ""

    def _spawn(self, args: list[str]) -> subprocess.Popen:
        """Start a detached process that survives our shell/session."""
        return subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            env=self._env(),
            start_new_session=True,
        )

    # -- Wayland compositor ------------------------------------------------
    def _host_wayland(self) -> Optional[str]:
        """If the host session already provides Wayland, use it directly."""
        disp = os.environ.get("WAYLAND_DISPLAY")
        if disp and (self._runtime_dir() / disp).exists():
            return disp
        for name in ("wayland-0", "wayland-1"):
            if (self._runtime_dir() / name).exists():
                return name
        return None

    def _compositor_alive(self) -> bool:
        sock = self._runtime_dir() / self.COMPOSITOR_SOCKET
        return sock.exists() and _proc_running("weston")

    def ensure_wayland(self) -> str:
        """Return a usable WAYLAND_DISPLAY name, starting weston if needed."""
        host = self._host_wayland()
        if host:
            return host

        if self._compositor_alive():
            return self.COMPOSITOR_SOCKET

        # Clean up any stale socket left by a dead/zombie weston.
        for name in (self.COMPOSITOR_SOCKET, self.COMPOSITOR_SOCKET + ".lock"):
            try:
                (self._runtime_dir() / name).unlink()
            except OSError:
                pass

        weston = shutil.which("weston")
        if not weston:
            raise BackendError(
                "未找到 weston。Android 需要 Wayland 合成器；"
                "请安装：sudo apt install weston"
            )
        self._runtime_dir().mkdir(parents=True, exist_ok=True)
        logf = open("/tmp/droiddeck-weston.log", "ab", buffering=0)
        if os.environ.get("DISPLAY"):
            backend = "--backend=x11"
        else:
            backend = "--backend=headless-backend.so"
        self._weston = subprocess.Popen(
            [weston, backend,
             f"--socket={self.COMPOSITOR_SOCKET}",
             "--width=1280", "--height=800", "--idle-time=0"],
            stdout=logf, stderr=logf, stdin=subprocess.DEVNULL,
            env=self._env(), start_new_session=True,
        )
        deadline = time.time() + 12
        while time.time() < deadline:
            if (self._runtime_dir() / self.COMPOSITOR_SOCKET).exists():
                return self.COMPOSITOR_SOCKET
            if self._weston.poll() is not None:
                raise BackendError("Wayland 合成器启动失败（weston 退出）")
            time.sleep(0.3)
        raise BackendError("Wayland 合成器启动超时")

    # -- state / lifecycle -------------------------------------------------
    def state(self) -> ContainerState:
        st = ContainerState()
        if not self.is_installed():
            return st
        out = self._run(["waydroid", "status"], timeout=8)
        if not out:
            return st
        st.initialized = "not initialized" not in out.lower()
        m = re.search(r"Session:\s*(\w+)", out)
        if m:
            st.session = m.group(1).upper()
        m = re.search(r"Container:\s*(\w+)", out)
        if m:
            st.container = m.group(1).upper()
        st.runtime_label = "LineageOS · Android 13"
        st.android_version = "13"
        return st

    def start_session(self, on_line: Callable[[str], None] | None = None) -> None:
        running = self.state().session == "RUNNING"
        if running and self._compositor_alive():
            return
        if running:
            # The session is still connected to a dead compositor; restart it
            # so it binds to the freshly (re)started weston. Otherwise app
            # launches hang for a long time.
            self._run(["waydroid", "session", "stop"], timeout=40)
            deadline = time.time() + 30
            while time.time() < deadline and self.state().session == "RUNNING":
                time.sleep(1)

        if shutil.which("systemctl"):
            subprocess.run(["systemctl", "start", "waydroid-container"],
                           capture_output=True, env=self._env())
        display = self.ensure_wayland()
        env = self._env()
        env["WAYLAND_DISPLAY"] = display
        self._session_proc = subprocess.Popen(
            ["waydroid", "session", "start"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, env=env, start_new_session=True,
        )
        deadline = time.time() + 120
        while time.time() < deadline:
            if self.state().session == "RUNNING":
                return
            time.sleep(1)
        raise BackendError("Waydroid 会话启动超时")

    def warm_up(self) -> None:
        """Best-effort: bring the session/compositor up in the background."""
        try:
            if self.state().initialized:
                self.start_session()
        except Exception:  # noqa: BLE001
            pass

    # -- apps --------------------------------------------------------------
    def list_apps(self) -> list[AndroidApp]:
        apps: list[AndroidApp] = []
        out = self._run(["waydroid", "app", "list"], timeout=25)
        if not out:
            return apps

        cur: dict = {}
        for raw in out.splitlines():
            line = raw.strip()
            low = line.lower()
            if low.startswith("name:"):
                cur["name"] = line.split(":", 1)[1].strip()
            elif low.startswith("packagename:") or low.startswith("package:"):
                cur["package"] = line.split(":", 1)[1].strip()
                if cur.get("package"):
                    apps.append(AndroidApp(
                        package=cur["package"],
                        name=cur.get("name") or cur["package"],
                    ))
                cur = {}

        entries = self._desktop_entries()
        for app in apps:
            info = entries.get(app.package)
            if not info:
                continue
            if info.get("Name"):
                app.name = info["Name"]
            if info.get("Icon"):
                app.icon_path = info["Icon"]
        return apps

    def _desktop_dirs(self) -> list[Path]:
        base = Path.home()
        dirs = [
            base / ".local/share/applications",
            Path("/usr/share/applications"),
        ]
        # Waydroid sometimes writes entries under its own data dir.
        dirs += list((base / ".local/share/waydroid").glob("**/applications"))
        return dirs

    def _desktop_entries(self) -> dict[str, dict]:
        found: dict[str, dict] = {}
        for d in self._desktop_dirs():
            if not d.is_dir():
                continue
            for f in d.glob("waydroid*.desktop"):
                try:
                    text = f.read_text(errors="ignore")
                except OSError:
                    continue
                m = re.search(r"^Exec=waydroid app launch (\S+)", text, re.M)
                if not m:
                    continue
                name = re.search(r"^Name=(.+)$", text, re.M)
                icon = re.search(r"^Icon=(.+)$", text, re.M)
                found[m.group(1)] = {
                    "Name": name.group(1).strip() if name else "",
                    "Icon": icon.group(1).strip() if icon else "",
                }
        return found

    def _resolve_installable(self, path: str) -> tuple[str, Optional[str]]:
        """Return (apk_to_install, temp_dir_to_clean)."""
        p = Path(path)
        suffix = p.suffix.lower()
        if suffix in (".hap", ".apppkg"):
            raise BackendError(
                "HarmonyOS NEXT 的 .hap 运行在 ArkTS/ArkVM 上，不是 Android 应用，"
                "无法在 Android 容器中运行。\n"
                "HarmonyOS 2/3/4 时代的应用实际是 Android APK，可以直接安装。"
            )
        if suffix in (".xapk", ".apks", ".apkm", ".zip"):
            import tempfile, zipfile
            tmp = tempfile.mkdtemp(prefix="droiddeck-")
            with zipfile.ZipFile(p) as z:
                apks = [n for n in z.namelist() if n.lower().endswith(".apk")]
                if not apks:
                    raise BackendError("安装包内没有找到 APK")
                base = next(
                    (n for n in apks if Path(n).name.lower() == "base.apk"), None
                )
                if base is None:
                    base = max(apks, key=lambda n: z.getinfo(n).file_size)
                z.extract(base, tmp)
                if on_line:
                    on_line(f"检测到拆分安装包，安装主 APK：{Path(base).name}")
            return str(Path(tmp) / base), tmp
        return str(p), None

    def _shared_dir(self) -> Path:
        """Host path that the container sees as /sdcard."""
        return Path.home() / ".local/share/waydroid/data/media/0"

    def unfreeze(self) -> None:
        """Wake the container if Waydroid suspended it (needed for installs)."""
        if shutil.which("lxc-unfreeze"):
            subprocess.run(
                ["lxc-unfreeze", "-P", "/var/lib/waydroid/lxc", "-n", "waydroid"],
                capture_output=True,
            )

    def install_apk(self, apk: str, on_line: Callable[[str], None] | None = None) -> None:
        if not Path(apk).is_file():
            raise BackendError(f"找不到安装包：{apk}")
        target, tmp = self._resolve_installable(apk)
        shared = self._shared_dir()
        dest = shared / f"droiddeck_install_{Path(target).name}"
        try:
            self.start_session(on_line)
            display = self.ensure_wayland()
            self.unfreeze()
            shared.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, dest)

            env = self._env()
            env["WAYLAND_DISPLAY"] = display
            # Installing through the container's own `pm` is far more reliable
            # than `waydroid app install` (which can fail silently).
            proc = subprocess.Popen(
                ["waydroid", "shell", "--", "pm", "install", "-r",
                 f"/sdcard/{dest.name}"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env,
            )
            assert proc.stdout is not None
            collected: list[str] = []
            for line in proc.stdout:
                collected.append(line)
                if on_line:
                    on_line(line.rstrip())
            proc.wait()
            output = "".join(collected)
            if "Success" not in output or "Failure" in output:
                last = output.strip().splitlines()[-1] if output.strip() else "未知错误"
                if "NO_MATCHING_ABIS" in output:
                    raise BackendError(
                        "安装失败：该应用只包含 ARM 原生库，当前容器缺少 ARM 转译层。"
                    )
                raise BackendError(f"安装失败：{last}")
        finally:
            try:
                dest.unlink()
            except OSError:
                pass
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)

    def remove_app(self, package: str) -> None:
        self._run(["waydroid", "app", "remove", package], timeout=60)

    def _launch(self, args: list[str]) -> None:
        display = self.ensure_wayland()
        env = self._env()
        env["WAYLAND_DISPLAY"] = display
        subprocess.Popen(args, env=env, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._focus_android_window()

    def _focus_android_window(self) -> None:
        """Raise the compositor window so the Android UI is visible on X11."""
        if not os.environ.get("DISPLAY"):
            return
        xdo = shutil.which("xdotool")
        if not xdo:
            return

        def _do() -> None:
            for _ in range(15):
                try:
                    ids = subprocess.run(
                        [xdo, "search", "--class", "weston"],
                        capture_output=True, text=True, timeout=3,
                    ).stdout.split()
                except (OSError, subprocess.SubprocessError):
                    return
                if ids:
                    wid = ids[-1]
                    for act in (["windowraise", wid],
                                ["windowactivate", "--sync", wid]):
                        subprocess.run([xdo, *act], capture_output=True, timeout=3)
                    return
                time.sleep(0.3)

        import threading
        threading.Thread(target=_do, daemon=True).start()

    def launch_app(self, package: str) -> None:
        self.start_session()
        self._launch(["waydroid", "app", "launch", package])

    def show_full_ui(self) -> None:
        self.start_session()
        self._launch(["waydroid", "show-full-ui"])


class NullBackend(AndroidBackend):
    """Placeholder for platforms without a runtime backend yet."""

    runtime_name = "当前平台暂不可用"

    _MSG = (
        "DroidDeck 目前依赖 Linux 上的 Waydroid 运行 Android 应用，"
        "当前平台暂不支持运行。你可以用它在 Linux 上运行；"
        "Windows / macOS 后端仍在计划中。"
    )

    def state(self) -> ContainerState:
        return ContainerState()

    def start_session(self, on_line=None) -> None:
        raise BackendError(self._MSG)

    def list_apps(self) -> list[AndroidApp]:
        return []

    def install_apk(self, apk, on_line=None) -> None:
        raise BackendError(self._MSG)

    def remove_app(self, package: str) -> None:
        raise BackendError(self._MSG)

    def launch_app(self, package: str) -> None:
        raise BackendError(self._MSG)

    def show_full_ui(self) -> None:
        raise BackendError(self._MSG)


def default_backend() -> AndroidBackend:
    import sys
    if sys.platform.startswith("linux"):
        return WaydroidBackend()
    return NullBackend()
