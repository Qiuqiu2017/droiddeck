"""Reusable widgets for DroidDeck."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import (
    QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QSizePolicy,
    QSpacerItem,
)

from . import theme


def make_chip(text: str, kind: str = "run") -> QLabel:
    chip = QLabel(text)
    chip.setObjectName("Chip")
    chip.setProperty("class", kind)
    chip.setObjectName({
        "run": "ChipRun", "stop": "ChipStop", "warn": "ChipWarn",
    }.get(kind, "ChipRun"))
    chip.setAlignment(Qt.AlignCenter)
    return chip


def android_fallback_icon(size: int = 48) -> QPixmap:
    """A simple rounded placeholder resembling a generic Android app icon."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    from PySide6.QtGui import QPainter, QColor, QBrush, QPainterPath
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, size, size, size * 0.22, size * 0.22)
    p.fillPath(path, QBrush(QColor(theme.SURFACE_2)))
    # little android head
    head = QPainterPath()
    r = size * 0.26
    cx = size / 2
    cy = size / 2 + size * 0.02
    head.addRoundedRect(cx - r, cy - r * 0.9, r * 2, r * 1.7, r * 0.5, r * 0.4)
    p.fillPath(head, QBrush(QColor(theme.ACCENT)))
    p.setBrush(QColor(theme.SURFACE_2))
    p.setPen(Qt.NoPen)
    for dx in (-r * 0.45, r * 0.45):
        p.drawEllipse(int(cx + dx - size * 0.02), int(cy - r * 0.35), int(size * 0.04), int(size * 0.04))
    p.end()
    return pm


def load_app_icon(icon_path: Optional[str], size: int = 48) -> QPixmap:
    if icon_path:
        p = Path(icon_path)
        if p.is_file():
            pm = QPixmap(str(p))
            if not pm.isNull():
                return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return android_fallback_icon(size)


class AppTile(QFrame):
    """A single installed-app tile."""

    launched = Signal(str)      # package
    removed = Signal(str)       # package
    compat_toggled = Signal(str, bool)  # package, enabled

    def __init__(self, package: str, name: str, icon_path: Optional[str],
                 compat: bool = False, parent=None):
        super().__init__(parent)
        self.package = package
        self.setObjectName("AppTile")
        self.setFixedHeight(88)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(14)

        icon = QLabel()
        icon.setFixedSize(52, 52)
        icon.setPixmap(load_app_icon(icon_path, 52))
        lay.addWidget(icon)

        text = QVBoxLayout()
        text.setSpacing(2)
        name_lbl = QLabel(name)
        name_lbl.setObjectName("AppName")
        name_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        pkg_lbl = QLabel(package)
        pkg_lbl.setObjectName("AppPkg")
        pkg_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        text.addWidget(name_lbl)
        text.addWidget(pkg_lbl)
        text.addStretch(1)
        lay.addLayout(text, 1)

        self.launch_btn = QPushButton("启动")
        self.launch_btn.setObjectName("Secondary")
        self.launch_btn.setFixedWidth(70)
        self.launch_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.launch_btn.clicked.connect(lambda: self.launched.emit(self.package))

        self.more_btn = QPushButton("卸载")
        self.more_btn.setObjectName("Ghost")
        self.more_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.more_btn.clicked.connect(lambda: self.removed.emit(self.package))

        self.compat_btn = QPushButton("触控")
        self.compat_btn.setObjectName("Ghost")
        self.compat_btn.setCheckable(True)
        self.compat_btn.setChecked(compat)
        self.compat_btn.setFixedWidth(56)
        self.compat_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.compat_btn.setToolTip(
            "触控兼容：把鼠标点击当作触摸事件（用于点击没反应的游戏），"
            "并假装 Wi‑Fi 网络。修改后需重启容器生效。")
        self.compat_btn.toggled.connect(
            lambda on: self.compat_toggled.emit(self.package, on))

        lay.addWidget(self.compat_btn)
        lay.addWidget(self.more_btn)
        lay.addWidget(self.launch_btn)

    def mouseDoubleClickEvent(self, event):
        self.launched.emit(self.package)


class Banner(QFrame):
    """Info banner that explicitly tells the user the Android runtime is a
    container — transparency is a design requirement, not an afterthought."""

    def __init__(self, backend_label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("Banner")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(14)

        badge = QLabel("ⓘ")
        badge.setStyleSheet(
            f"color:{theme.INFO}; font-size:22px; font-weight:800;"
        )
        badge.setFixedWidth(26)
        badge.setAlignment(Qt.AlignTop)
        lay.addWidget(badge)

        col = QVBoxLayout()
        col.setSpacing(3)
        title = QLabel(f"基于 {backend_label} 运行（Android 容器）")
        title.setObjectName("H2")
        desc = QLabel(
            "应用运行在隔离的 Android 容器中，并非原生 Linux 程序。"
            "应用界面与操作体验和安卓设备一致。"
        )
        desc.setObjectName("DimSmall")
        desc.setWordWrap(True)
        col.addWidget(title)
        col.addWidget(desc)
        lay.addLayout(col, 1)
