"""A generic modal dialog that runs a background callable and shows progress."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QLabel, QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout,
    QHBoxLayout,
)

from . import theme


class _Worker(QThread):
    line = Signal(str)
    done = Signal(bool, str)

    def __init__(self, fn: Callable[[Callable[[str], None]], None]):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.fn(self.line.emit)
            self.done.emit(True, "")
        except Exception as e:  # noqa: BLE001
            self.done.emit(False, str(e))


class TaskDialog(QDialog):
    def __init__(self, title: str, fn: Callable[[Callable[[str], None]], None],
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedWidth(460)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 22, 22, 18)
        lay.setSpacing(12)

        head = QLabel(title)
        head.setObjectName("H2")
        lay.addWidget(head)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        lay.addWidget(self.progress)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(160)
        self.log.setStyleSheet(
            f"background:{theme.BG}; border:1px solid {theme.BORDER};"
            f"border-radius:10px; color:{theme.TEXT_DIM}; font-size:11px;"
        )
        lay.addWidget(self.log)

        self.status = QLabel("")
        self.status.setObjectName("DimSmall")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        row = QHBoxLayout()
        row.addStretch(1)
        self.close_btn = QPushButton("关闭")
        self.close_btn.setObjectName("Secondary")
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)
        row.addWidget(self.close_btn)
        lay.addLayout(row)

        self.worker = _Worker(fn)
        self.worker.line.connect(self.log.appendPlainText)
        self.worker.done.connect(self._on_done)
        self.worker.start()

    def _on_done(self, ok: bool, msg: str):
        self.progress.hide()
        if ok:
            self.status.setText("✓ 完成")
            self.status.setStyleSheet(f"color:{theme.ACCENT}; font-weight:700;")
        else:
            self.status.setText(f"✗ {msg}")
            self.status.setStyleSheet(f"color:{theme.DANGER}; font-weight:700;")
        self.close_btn.setEnabled(True)
