"""Entry point: python -m droiddeck"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from . import theme
from .backend import default_backend
from .main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("DroidDeck")
    app.setApplicationDisplayName("DroidDeck")
    app.setStyleSheet(theme.stylesheet())

    backend = default_backend()
    win = MainWindow(backend)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
