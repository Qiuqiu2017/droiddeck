"""Entry point: python -m droiddeck"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from . import theme
from .backend import default_backend
from .main_window import MainWindow

_SINGLE_KEY = "droiddeck-single"


def _try_activate_existing() -> bool:
    """If another instance is running, ask it to show itself and return True."""
    try:
        from PySide6.QtNetwork import QLocalSocket
    except Exception:  # noqa: BLE001
        return False
    sock = QLocalSocket()
    sock.connectToServer(_SINGLE_KEY)
    if sock.waitForConnected(200):
        sock.write(b"show")
        sock.flush()
        sock.waitForBytesWritten(300)
        return True
    return False


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("DroidDeck")
    app.setApplicationDisplayName("DroidDeck")
    app.setStyleSheet(theme.stylesheet())

    if _try_activate_existing():
        return 0

    server = None
    try:
        from PySide6.QtNetwork import QLocalServer
        server = QLocalServer()
        server.removeServer(_SINGLE_KEY)  # clear a stale socket
        server.listen(_SINGLE_KEY)
    except Exception:  # noqa: BLE001
        server = None

    backend = default_backend()
    win = MainWindow(backend)

    if server is not None:
        def on_new_connection():
            conn = server.nextPendingConnection()
            if conn is not None:
                conn.readAll()
                conn.disconnectFromServer()
            win.showNormal()
            win.raise_()
            win.activateWindow()

        server.newConnection.connect(on_new_connection)

    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
