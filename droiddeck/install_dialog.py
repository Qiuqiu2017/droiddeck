"""The APK install dialog — styled to resemble the native Android package
installer (large rounded card, app icon, name, size, primary install button).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar,
    QPushButton, QVBoxLayout, QWidget,
)

from . import theme
from .widgets import load_app_icon
from .backend import AndroidBackend, BackendError


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def extract_apk_info(apk: str) -> dict:
    """Best-effort metadata extraction from an APK without extra deps."""
    info = {"package": "", "label": "", "version": ""}
    aapt = shutil.which("aapt") or shutil.which("aapt2")
    if aapt:
        try:
            out = subprocess.run(
                [aapt, "dump", "badging", apk],
                capture_output=True, text=True, timeout=15,
            ).stdout
            m = re.search(r"package: name='([^']+)'", out)
            if m:
                info["package"] = m.group(1)
            m = re.search(r"application-label:'([^']*)'", out)
            if m:
                info["label"] = m.group(1)
            m = re.search(r"versionName='([^']+)'", out)
            if m:
                info["version"] = m.group(1)
        except (OSError, subprocess.SubprocessError):
            pass

    if not info["package"]:
        # Heuristic scan of the binary manifest string pool.
        try:
            blob = Path(apk).read_bytes()[:2_000_000]
            candidates = re.findall(rb"([a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+){2,})", blob)
            scored: dict[bytes, int] = {}
            for c in candidates:
                scored[c] = scored.get(c, 0) + 1
            ranked = sorted(scored, key=lambda k: (-scored[k], -len(k)))
            if ranked:
                info["package"] = ranked[0].decode("ascii", "ignore")
        except OSError:
            pass
    return info


class InstallWorker(QThread):
    line = Signal(str)
    done = Signal(bool, str)

    def __init__(self, backend: AndroidBackend, apk: str):
        super().__init__()
        self.backend = backend
        self.apk = apk

    def run(self):
        try:
            self.backend.install_apk(self.apk, on_line=self.line.emit)
            self.done.emit(True, "")
        except BackendError as e:
            self.done.emit(False, str(e))
        except Exception as e:  # noqa: BLE001
            self.done.emit(False, f"安装异常：{e}")


class InstallDialog(QDialog):
    installed = Signal()

    def __init__(self, backend: AndroidBackend, apk: str, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.apk = apk
        self.setWindowTitle("安装应用")
        self.setModal(True)
        self.setFixedWidth(440)
        self.setWindowFlag(Qt.FramelessWindowHint, False)

        info = extract_apk_info(apk)
        size = os.path.getsize(apk) if os.path.exists(apk) else 0
        display = info["label"] or Path(apk).stem

        root = QWidget()
        root.setObjectName("InstallerRoot")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)

        lay = QVBoxLayout(root)
        lay.setContentsMargins(28, 28, 28, 24)
        lay.setSpacing(16)

        # header: icon + name
        head = QHBoxLayout()
        head.setSpacing(16)
        icon = QLabel()
        icon.setFixedSize(72, 72)
        icon.setPixmap(load_app_icon(None, 72))
        head.addWidget(icon)

        meta = QVBoxLayout()
        meta.setSpacing(4)
        title = QLabel(display)
        title.setObjectName("InstallerTitle")
        title.setWordWrap(True)
        pkg = QLabel(info["package"] or Path(apk).name)
        pkg.setObjectName("InstallerPkg")
        version = QLabel(
            (f"版本 {info['version']}  ·  " if info["version"] else "") + human_size(size)
        )
        version.setObjectName("DimSmall")
        meta.addWidget(title)
        meta.addWidget(pkg)
        meta.addWidget(version)
        head.addLayout(meta, 1)
        lay.addLayout(head)

        # transparency note
        note = QLabel("即将安装到 Android 容器（Waydroid）。应用仅在本机运行。")
        note.setWordWrap(True)
        note.setStyleSheet(
            f"background:{theme.SURFACE_2}; border-radius:10px; padding:10px 12px;"
            f"color:{theme.TEXT_DIM}; font-size:12px;"
        )
        lay.addWidget(note)

        # progress + log
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminate
        self.progress.hide()
        lay.addWidget(self.progress)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(90)
        self.log.setStyleSheet(
            f"background:{theme.BG}; border:1px solid {theme.BORDER};"
            f"border-radius:10px; color:{theme.TEXT_DIM}; font-size:11px;"
        )
        self.log.hide()
        lay.addWidget(self.log)

        self.status = QLabel("")
        self.status.setObjectName("DimSmall")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        # buttons
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("Secondary")
        self.cancel_btn.clicked.connect(self.reject)
        self.install_btn = QPushButton("安装")
        self.install_btn.setObjectName("Primary")
        self.install_btn.setMinimumWidth(110)
        self.install_btn.clicked.connect(self._start)
        btns.addWidget(self.cancel_btn)
        btns.addWidget(self.install_btn)
        lay.addLayout(btns)

        self.worker: InstallWorker | None = None

    def _start(self):
        self.install_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.progress.show()
        self.log.show()
        self.status.setText("正在安装…")
        self.worker = InstallWorker(self.backend, self.apk)
        self.worker.line.connect(self._on_line)
        self.worker.done.connect(self._on_done)
        self.worker.start()

    def _on_line(self, text: str):
        self.log.appendPlainText(text)

    def _on_done(self, ok: bool, msg: str):
        self.progress.hide()
        if ok:
            self.status.setText("✓ 安装完成")
            self.status.setStyleSheet(f"color:{theme.ACCENT}; font-weight:700;")
            self.install_btn.setText("完成")
            self.install_btn.setEnabled(True)
            self.install_btn.clicked.disconnect()
            self.install_btn.clicked.connect(self._accept_done)
            self.cancel_btn.setEnabled(True)
            self.installed.emit()
        else:
            self.status.setText(f"✗ {msg}")
            self.status.setStyleSheet(f"color:{theme.DANGER}; font-weight:700;")
            self.install_btn.setEnabled(True)
            self.install_btn.setText("重试")
            self.install_btn.clicked.disconnect()
            self.install_btn.clicked.connect(self._start)
            self.cancel_btn.setEnabled(True)

    def _accept_done(self):
        self.accept()
