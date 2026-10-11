"""Root environment management for DroidDeck.

Installs Magisk (Delta) into the Waydroid container to provide a root
environment, plus the Shamiko module for hiding root from apps.  This is a
native re-implementation (GPL-3.0) of the well-known install steps so DroidDeck
does not depend on an external script at runtime.
"""

from __future__ import annotations

import gzip
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

from .backend import AndroidBackend, BackendError


LineCb = Callable[[str], None]

# --- download sources (mirrored through a GitHub proxy when needed) ---------
MAGISK_URL = "https://github.com/mistrmochov/magiskdeltaorig/raw/main/app-release.apk"
SHAMIKO_URL = (
    "https://github.com/LSPosed/LSPosed.github.io/releases/download/"
    "shamiko-161/Shamiko-v0.7-161-release.zip"
)
PROXIES = ["", "https://gh-proxy.com/", "https://ghproxy.net/"]

BOOTANIM_ORIG = """
service bootanim /system/bin/bootanimation
    class core animation
    user graphics
    group graphics audio
    disabled
    oneshot
    ioprio rt 0
    task_profiles MaxPerformance
    
"""

BOOTANIM_MAGISK = """
on post-fs-data
    start logd
    exec u:r:su:s0 root root -- /system/etc/init/magisk/magiskpolicy --live --magisk
    exec u:r:magisk:s0 root root -- /system/etc/init/magisk/magiskpolicy --live --magisk
    exec u:r:update_engine:s0 root root -- /system/etc/init/magisk/magiskpolicy --live --magisk
    mkdir /dev/magisk_iqeoVo2mDrO 700
    exec u:r:su:s0 root root -- /system/etc/init/magisk/magisk64 --auto-selinux --setup-sbin /system/etc/init/magisk /dev/magisk_iqeoVo2mDrO
    exec u:r:su:s0 root root -- /dev/magisk_iqeoVo2mDrO/magisk --auto-selinux --post-fs-data

on nonencrypted
    exec u:r:su:s0 root root -- /dev/magisk_iqeoVo2mDrO/magisk --auto-selinux --service

on property:vold.decrypt=trigger_restart_framework
    exec u:r:su:s0 root root -- /dev/magisk_iqeoVo2mDrO/magisk --auto-selinux --service

on property:sys.boot_completed=1
    mkdir /data/adb/magisk 755
    exec u:r:su:s0 root root -- /dev/magisk_iqeoVo2mDrO/magisk --auto-selinux --boot-complete
   
on property:init.svc.zygote=restarting
    exec u:r:su:s0 root root -- /dev/magisk_iqeoVo2mDrO/magisk --auto-selinux --zygote-restart
   
on property:init.svc.zygote=stopped
    exec u:r:su:s0 root root -- /dev/magisk_iqeoVo2mDrO/magisk --auto-selinux --zygote-restart
    """


class RootEnv:
    def __init__(self, backend: AndroidBackend):
        self.backend = backend
        self.overlay = Path("/var/lib/waydroid/overlay")
        self.overlay_rw = Path("/var/lib/waydroid/overlay_rw")
        self.data = Path.home() / ".local/share/waydroid/data"
        self.cache = Path.home() / ".cache" / "droiddeck"
        self.arch = "x86_64"

    # -- status ------------------------------------------------------------
    @property
    def magisk_dir(self) -> Path:
        return self.overlay / "system/etc/init/magisk"

    def magisk_installed(self) -> bool:
        return (self.magisk_dir / "magisk64").exists()

    def magisk_running(self) -> bool:
        out = self.backend._run(
            ["waydroid", "shell", "--", "su", "-c", "magisk -v"], timeout=15
        )
        return "magisk" in out.lower()

    # -- download ----------------------------------------------------------
    def _download(self, url: str, name: str, on_line: Optional[LineCb]) -> Path:
        dest = self.cache / name
        if dest.exists() and dest.stat().st_size > 100_000:
            return dest
        self.cache.mkdir(parents=True, exist_ok=True)
        last_err: Exception | None = None
        for prefix in PROXIES:
            try:
                if on_line:
                    on_line(f"下载 {name} …")
                with urllib.request.urlopen(prefix + url, timeout=60) as r, \
                        open(dest, "wb") as f:
                    shutil.copyfileobj(r, f)
                if dest.stat().st_size > 100_000:
                    return dest
            except Exception as e:  # noqa: BLE001
                last_err = e
                continue
        raise BackendError(f"下载失败：{name}（{last_err}）")

    # -- install Magisk ----------------------------------------------------
    def _stop(self, on_line: Optional[LineCb]) -> None:
        if on_line:
            on_line("停止容器会话 …")
        self.backend._run(["waydroid", "session", "stop"], timeout=60)
        deadline = time.time() + 30
        while time.time() < deadline and self.backend.state().session == "RUNNING":
            time.sleep(1)

    def _perm(self, path: Path, under_magisk: bool) -> None:
        if under_magisk:
            uid, gid, dirmode, filemode = 0, 2000, 0o755, 0o755
        else:
            uid, gid, dirmode, filemode = 0, 0, 0o755, 0o644
        try:
            os.chown(path, uid, gid)
            mode = os.stat(path).st_mode
            mode |= dirmode if path.is_dir() else filemode
            os.chmod(path, mode)
        except OSError:
            pass

    def _set_perms_recursive(self, root: Path, under_magisk: bool) -> None:
        self._perm(root, under_magisk)
        for base, dirs, files in os.walk(root):
            for d in dirs:
                self._perm(Path(base) / d, under_magisk)
            for f in files:
                self._perm(Path(base) / f, under_magisk)

    def install_magisk(self, on_line: Optional[LineCb] = None) -> None:
        """Install Magisk Delta into the system overlay (container stopped)."""
        apk = self._download(MAGISK_URL, "magisk.apk", on_line)
        self._stop(on_line)

        if on_line:
            on_line("解压 Magisk …")
        tmp = Path(tempfile.mkdtemp(prefix="droiddeck-magisk-"))
        with zipfile.ZipFile(apk) as z:
            z.extractall(tmp)
        try:
            self.magisk_dir.mkdir(parents=True, exist_ok=True)

            lib_dir = tmp / "lib" / self.arch
            for f in lib_dir.iterdir():
                m = re.search(r"lib(.*)\.so", f.name)
                if m:
                    shutil.copyfile(f, self.magisk_dir / m.group(1))
            shutil.copyfile(apk, self.magisk_dir / "magisk.apk")
            chrome = tmp / "assets" / "chromeos"
            if chrome.is_dir():
                shutil.copytree(chrome, self.magisk_dir / "chromeos",
                                dirs_exist_ok=True)
            for f in ("addon.d.sh", "boot_patch.sh", "stub.apk",
                      "util_functions.sh"):
                src = tmp / "assets" / f
                if src.exists():
                    shutil.copyfile(src, self.magisk_dir / f)

            if on_line:
                on_line("写入 init 脚本 …")
            bootanim = self.overlay / "system/etc/init/bootanim.rc"
            bootanim.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(str(bootanim) + ".gz", "wb") as fh:
                fh.write(BOOTANIM_ORIG.encode("utf-8"))
            bootanim.write_text(BOOTANIM_ORIG + BOOTANIM_MAGISK)

            # Force overlay upper layers to be rebuilt.
            for rel in (
                "system/system/etc/init/bootanim.rc",
                "system/system/etc/init/bootanim.rc.gz",
                "system/system/etc/init/magisk",
                "system/system/addon.d/99-magisk.sh",
            ):
                p = self.overlay_rw / rel
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                elif p.exists():
                    p.unlink()

            if on_line:
                on_line("设置权限 …")
            self._set_perms_recursive(self.magisk_dir, under_magisk=True)
            self._perm(bootanim, under_magisk=False)

            # Seed /data/adb/magisk so the daemon finds its files.
            adb_magisk = self.data / "adb" / "magisk"
            shutil.copytree(self.magisk_dir, adb_magisk, dirs_exist_ok=True)

            if on_line:
                on_line("Magisk 安装完成")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # -- Shamiko hide module ----------------------------------------------
    def install_shamiko(self, on_line: Optional[LineCb] = None) -> None:
        """Install Shamiko as a Magisk module (requires Magisk running)."""
        zips = self._download(SHAMIKO_URL, "shamiko.zip", on_line)
        shared = Path.home() / ".local/share/waydroid/data/media/0"
        shared.mkdir(parents=True, exist_ok=True)
        # Unique name so Android's /sdcard FUSE cache never serves a stale zip.
        fname = f"droiddeck_shamiko_{os.getpid()}_{int(time.time())}.zip"
        dest = shared / fname
        shutil.copyfile(zips, dest)
        try:
            if on_line:
                on_line("安装 Shamiko 模块 …")
            out = self.backend._run(
                ["waydroid", "shell", "--", "su", "-c",
                 f"magisk --install-module /sdcard/{fname}"],
                timeout=120,
            )
            if on_line and out.strip():
                on_line(out.strip())
        finally:
            try:
                dest.unlink()
            except OSError:
                pass

    def enable_hiding(self, on_line: Optional[LineCb] = None) -> None:
        """Turn on Zygisk + MagiskHide in the Magisk database."""
        if on_line:
            on_line("启用 Zygisk 与 MagiskHide …")
        for key in ("zygisk", "magiskhide"):
            self.backend._run(
                ["waydroid", "shell", "--", "su", "-c",
                 f"magisk --sqlite \"REPLACE INTO settings (key,value) "
                 f"VALUES('{key}','1')\""],
                timeout=30,
            )

    # -- 防格机保护模块 ----------------------------------------------------
    @property
    def armor_dir(self) -> Path:
        return Path(__file__).parent / "assets" / "modules" / "armor"

    def armor_installed(self) -> bool:
        out = self.backend._run(
            ["waydroid", "shell", "--", "su", "-c",
             "ls /data/adb/modules/droiddeck_armor/module.prop"],
            timeout=15,
        )
        return "module.prop" in out

    def install_armor(self, on_line: Optional[LineCb] = None) -> None:
        """Install the anti-wipe (防格机) protection Magisk module."""
        src = self.armor_dir
        if not (src / "module.prop").is_file():
            raise BackendError("未找到防格机模块资源")
        if on_line:
            on_line("打包防格机模块 …")
        tmp = Path(tempfile.mkdtemp(prefix="droiddeck-armor-"))
        zip_path = tmp / "droiddeck-armor.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for f in src.rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(src))  # module.prop at zip root
        shared = Path.home() / ".local/share/waydroid/data/media/0"
        shared.mkdir(parents=True, exist_ok=True)
        fname = f"droiddeck_armor_{os.getpid()}_{int(time.time())}.zip"
        dest = shared / fname
        shutil.copyfile(zip_path, dest)
        try:
            if on_line:
                on_line("安装防格机模块 …")
            out = self.backend._run(
                ["waydroid", "shell", "--", "su", "-c",
                 f"magisk --install-module /sdcard/{fname}"],
                timeout=120,
            )
            if on_line and out.strip():
                on_line(out.strip())
        finally:
            try:
                dest.unlink()
            except OSError:
                pass
            shutil.rmtree(tmp, ignore_errors=True)

    # -- full flow ---------------------------------------------------------
    def ensure_root(self, on_line: Optional[LineCb] = None,
                    with_armor: bool = True) -> None:
        if not self.magisk_installed():
            self.install_magisk(on_line)
            if on_line:
                on_line("重启容器 …")
            self.backend.start_session()
            # Wait for Android to finish booting before touching Magisk.
            deadline = time.time() + 180
            while time.time() < deadline:
                out = self.backend._run(
                    ["waydroid", "shell", "--", "getprop", "sys.boot_completed"],
                    timeout=10,
                ).strip()
                if out == "1":
                    break
                time.sleep(3)
        else:
            self.backend.start_session()

        try:
            self.install_shamiko(on_line)
            self.enable_hiding(on_line)
            if with_armor:
                self.install_armor(on_line)
        except BackendError as e:
            if on_line:
                on_line(f"模块配置：{e}")
        # Pre-allow root for all installed apps so su never blocks.
        grant = getattr(self.backend, "_grant_all_root", None)
        if grant:
            grant()
        if on_line:
            on_line("Root 环境就绪")
