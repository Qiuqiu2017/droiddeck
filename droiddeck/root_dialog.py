"""Start-up dialog asking whether to enable a root environment."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

from . import theme


class RootPromptDialog(QDialog):
    """Asked once per start-up.  The checkbox is checked by default."""

    def __init__(self, default_checked: bool = True, installed: bool = False,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Root 环境")
        self.setModal(True)
        self.setFixedWidth(460)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 20)
        lay.setSpacing(14)

        title = QLabel("是否启用 Root 环境？")
        title.setObjectName("H1")
        lay.addWidget(title)

        desc = QLabel(
            "启用后将为 Android 容器安装 <b>Magisk</b> 提供 root，"
            "并安装 <b>Shamiko</b> 隐藏模块，用于对指定应用隐藏 root/环境信息。"
            + ("<br><br>当前已检测到已安装的 Root 环境。" if installed else "")
        )
        desc.setWordWrap(True)
        desc.setObjectName("Dim")
        lay.addWidget(desc)

        self.check = QCheckBox("启用 Root 环境")
        self.check.setChecked(default_checked)
        self.check.setStyleSheet("font-weight:600; padding:6px 0;")
        lay.addWidget(self.check)

        row = QHBoxLayout()
        row.addStretch(1)
        later = QPushButton("稍后再说")
        later.setObjectName("Secondary")
        later.clicked.connect(self.reject)
        ok = QPushButton("确定")
        ok.setObjectName("Primary")
        ok.setMinimumWidth(110)
        ok.clicked.connect(self.accept)
        row.addWidget(later)
        row.addWidget(ok)
        lay.addLayout(row)

    @property
    def enabled(self) -> bool:
        return self.check.isChecked()
