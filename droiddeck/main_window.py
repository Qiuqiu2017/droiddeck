"""Main application window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QStackedWidget,
    QVBoxLayout, QWidget,
)

from . import theme
from .backend import (
    AndroidBackend, BackendError, ContainerState, WaydroidBackend,
    default_backend,
)
from .install_dialog import InstallDialog
from .widgets import AppTile, Banner, make_chip
from .settings import Settings
from .root_dialog import RootPromptDialog
from .taskdialog import TaskDialog
from .rootenv import RootEnv
from . import updater
from . import __version__


class DataWorker(QThread):
    """Fetch container state + app list off the UI thread."""

    ready = Signal(object, object)  # ContainerState, list[AndroidApp]

    def __init__(self, backend: AndroidBackend, parent=None):
        super().__init__(parent)
        self.backend = backend

    def run(self):
        try:
            st = self.backend.state()
        except Exception:  # noqa: BLE001
            st = ContainerState()
        try:
            apps = self.backend.list_apps() if st.session == "RUNNING" else []
        except Exception:  # noqa: BLE001
            apps = []
        self.ready.emit(st, apps)


class WarmUpWorker(QThread):
    """Bring the session/compositor up in the background at startup."""

    def __init__(self, backend: AndroidBackend, parent=None):
        super().__init__(parent)
        self.backend = backend

    def run(self):
        try:
            self.backend.warm_up()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass


class UpdateWorker(QThread):
    """Check the update server in the background."""

    found = Signal(object)      # updater.UpdateInfo
    none = Signal()
    failed = Signal(str)

    def __init__(self, manual: bool = False, parent=None):
        super().__init__(parent)
        self.manual = manual

    def run(self):
        info = updater.check()
        if info.error:
            self.failed.emit(info.error)
            return
        if updater.is_newer(info.version, __version__):
            self.found.emit(info)
        else:
            self.none.emit()


class MainWindow(QWidget):
    def __init__(self, backend: AndroidBackend | None = None):
        super().__init__()
        self.backend = backend or default_backend()
        self.settings = Settings()
        self.rootenv = RootEnv(self.backend) if isinstance(
            self.backend, WaydroidBackend) else None
        self._data_worker: DataWorker | None = None
        self._warm_worker: WarmUpWorker | None = None

        self.setObjectName("Root")
        self.setWindowTitle("DroidDeck — Android 应用运行器")
        self.resize(1040, 680)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_library_page())
        self.stack.addWidget(self._build_about_page())
        root.addWidget(self.stack, 1)

        # First refresh only — do NOT auto-start the container. The user
        # decides when to bring Android up via the "启动容器" button.
        self._refresh()

        self.timer = QTimer(self)
        self.timer.setInterval(4000)
        self.timer.timeout.connect(self._refresh)
        self.timer.start()

        QTimer.singleShot(400, self._prompt_root)
        QTimer.singleShot(3000, lambda: self._check_updates(manual=False))

    # --------------------------------------------------------- update check
    def _check_updates(self, manual: bool = True):
        w = UpdateWorker(manual, self)
        w.found.connect(lambda info: self._show_update(info))
        if manual:
            w.none.connect(lambda: QMessageBox.information(
                self, "检查更新", f"当前已是最新版本（v{__version__}）。"))
            w.failed.connect(lambda e: QMessageBox.warning(
                self, "检查更新", f"无法连接更新服务器：{e}"))
        w.start()
        self._update_worker = w  # keep a reference

    def _show_update(self, info: "updater.UpdateInfo"):
        box = QMessageBox(self)
        box.setWindowTitle("发现新版本")
        box.setText(f"发现新版本 v{info.version}（当前 v{__version__}）")
        if info.notes:
            box.setInformativeText(info.notes)
        go = box.addButton("前往下载", QMessageBox.AcceptRole)
        box.addButton("稍后", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is go:
            url = info.download_url() or info.page_url
            if url:
                from PySide6.QtGui import QDesktopServices
                from PySide6.QtCore import QUrl
                QDesktopServices.openUrl(QUrl(url))

    # ------------------------------------------------------------ root env
    def _prompt_root(self):
        if self.rootenv is None:
            return
        installed = self.rootenv.magisk_installed()
        dlg = RootPromptDialog(
            default_checked=bool(self.settings.get("root_enabled", True)),
            installed=installed,
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        self.settings.set("root_enabled", dlg.enabled)
        if not dlg.enabled:
            return
        if not installed or not self.settings.get("root_ready", False):
            TaskDialog("配置 Root 环境",
                       self._do_root_install, self).exec()
            self.settings.set("root_ready", True)
            self._refresh()

    def _do_root_install(self, log):
        self.rootenv.ensure_root(log)

    # ------------------------------------------------------------------ UI
    def _build_sidebar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("Sidebar")
        bar.setFixedWidth(232)
        lay = QVBoxLayout(bar)
        lay.setContentsMargins(18, 22, 18, 18)
        lay.setSpacing(8)

        brand = QLabel("DroidDeck")
        brand.setObjectName("Brand")
        sub = QLabel("Android 应用运行器")
        sub.setObjectName("BrandSub")
        lay.addWidget(brand)
        lay.addWidget(sub)
        lay.addSpacing(18)

        self.nav_buttons: list[QPushButton] = []
        group = QButtonGroup(self)
        for label, target in [("应用库", 0), ("关于", 1)]:
            b = QPushButton(label)
            b.setObjectName("Nav")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, t=target: self.stack.setCurrentIndex(t))
            group.addButton(b)
            lay.addWidget(b)
            self.nav_buttons.append(b)
        self.nav_buttons[0].setChecked(True)

        lay.addStretch(1)
        self.status_title = QLabel("容器状态")
        self.status_title.setObjectName("DimSmall")
        self.status_chip = make_chip("检测中…", "warn")
        self.status_chip.setFixedHeight(26)
        lay.addWidget(self.status_title)
        lay.addWidget(self.status_chip)

        self.session_btn = QPushButton("启动容器")
        self.session_btn.setObjectName("Secondary")
        self.session_btn.clicked.connect(self._start_session)
        lay.addWidget(self.session_btn)
        return bar

    def _build_library_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(26, 24, 26, 24)
        lay.setSpacing(16)

        header = QHBoxLayout()
        col = QVBoxLayout()
        h1 = QLabel("应用库")
        h1.setObjectName("H1")
        hint = QLabel("安装并运行 Android 应用（APK）")
        hint.setObjectName("Dim")
        col.addWidget(h1)
        col.addWidget(hint)
        header.addLayout(col)
        header.addStretch(1)

        self.open_desktop_btn = QPushButton("打开 Android 桌面")
        self.open_desktop_btn.setObjectName("Secondary")
        self.open_desktop_btn.clicked.connect(self._open_desktop)
        self.install_btn = QPushButton("＋  安装 APK")
        self.install_btn.setObjectName("Primary")
        self.install_btn.clicked.connect(self._pick_apk)
        header.addWidget(self.open_desktop_btn)
        header.addWidget(self.install_btn)
        lay.addLayout(header)

        lay.addWidget(Banner(self.backend.runtime_name))

        self.grid_card = QFrame()
        self.grid_card.setObjectName("Card")
        self.grid_layout = QGridLayout(self.grid_card)
        self.grid_layout.setContentsMargins(18, 18, 18, 18)
        self.grid_layout.setSpacing(14)
        self.grid_layout.setColumnStretch(0, 1)
        self.grid_layout.setColumnStretch(1, 1)

        self.empty_hint = QLabel("正在加载…")
        self.empty_hint.setObjectName("Dim")
        self.empty_hint.setAlignment(Qt.AlignCenter)
        self.empty_hint.setWordWrap(True)
        self.grid_layout.addWidget(self.empty_hint, 0, 0, 1, 2)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(self.grid_card)
        lay.addWidget(scroll, 1)
        return page

    def _build_about_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(26, 24, 26, 24)
        lay.setSpacing(12)
        h1 = QLabel("关于")
        h1.setObjectName("H1")
        lay.addWidget(h1)
        about = QLabel(
            "<p><b>DroidDeck</b> 是一个跨平台的 Android 应用运行器前端。</p>"
            "<p>在 Linux 上，它通过 <b>Waydroid</b> 容器运行安卓应用，"
            "应用运行在隔离的 Android 系统（LineageOS）中。</p>"
            "<p>本软件为开源项目，遵循 GPL-3.0 许可。</p>"
        )
        about.setWordWrap(True)
        about.setObjectName("Dim")
        lay.addWidget(about)

        row = QHBoxLayout()
        self.version_lbl = QLabel(f"当前版本 v{__version__}")
        self.version_lbl.setObjectName("DimSmall")
        row.addWidget(self.version_lbl)
        row.addStretch(1)
        check_btn = QPushButton("检查更新")
        check_btn.setObjectName("Secondary")
        check_btn.clicked.connect(lambda: self._check_updates(manual=True))
        row.addWidget(check_btn)
        lay.addLayout(row)
        lay.addStretch(1)
        return page

    # ------------------------------------------------------------- actions
    def _pick_apk(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择安装包", str(Path.home()),
            "Android / 鸿蒙 安装包 (*.apk *.apks *.xapk *.hap);;所有文件 (*)",
        )
        if not path:
            return
        if path.lower().endswith(".hap"):
            QMessageBox.information(
                self, "暂不支持",
                "HarmonyOS NEXT 的 .hap 安装包运行在 ArkTS/ArkVM 上，"
                "不是 Android 应用，无法在 Android 容器中运行。\n\n"
                "HarmonyOS 2/3/4 时代的应用实际是 Android APK，可以直接安装。",
            )
            return
        dlg = InstallDialog(self.backend, path, self)
        dlg.installed.connect(self._refresh)
        dlg.exec()
        self._refresh()

    def _open_desktop(self):
        try:
            self.backend.show_full_ui()
        except BackendError as e:
            self._error(str(e))

    def _start_session(self):
        self.status_chip.setText("启动中…")
        self._set_chip_class(self.status_chip, "warn")
        self.session_btn.setEnabled(False)
        self._warm_worker = WarmUpWorker(self.backend, self)
        self._warm_worker.finished.connect(lambda: (self.session_btn.setEnabled(True), self._refresh()))
        self._warm_worker.start()

    # ------------------------------------------------------------- refresh
    def _refresh(self):
        if self._data_worker and self._data_worker.isRunning():
            return  # don't stack up requests
        self._data_worker = DataWorker(self.backend, self)
        self._data_worker.ready.connect(self._on_data)
        self._data_worker.start()

    def _on_data(self, st: ContainerState, apps: list):
        self._update_status(st)
        self._render_apps(st, apps)

    def _update_status(self, st: ContainerState):
        if not st.initialized:
            self.status_chip.setText("未初始化")
            self._set_chip_class(self.status_chip, "warn")
        elif st.session == "RUNNING":
            self.status_chip.setText("运行中")
            self._set_chip_class(self.status_chip, "run")
        else:
            self.status_chip.setText(st.session.title())
            self._set_chip_class(self.status_chip, "stop")
        self.open_desktop_btn.setEnabled(st.initialized)
        self.session_btn.setEnabled(st.session != "RUNNING")

    def _set_chip_class(self, chip: QLabel, kind: str):
        chip.setObjectName({"run": "ChipRun", "stop": "ChipStop", "warn": "ChipWarn"}[kind])
        chip.style().unpolish(chip)
        chip.style().polish(chip)

    def _render_apps(self, st: ContainerState, apps: list):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w and w is not self.empty_hint:
                w.deleteLater()

        if not apps:
            if not st.initialized:
                msg = "Waydroid 尚未初始化。"
            elif st.session != "RUNNING":
                msg = "容器未运行，正在启动或点击左下角「启动容器」。"
            else:
                msg = "尚未安装任何应用，点击右上角「安装 APK」开始。"
            self.empty_hint.setText(msg)
            self.empty_hint.show()
            self.grid_layout.addWidget(self.empty_hint, 0, 0, 1, 2)
            return

        self.empty_hint.hide()
        cols = 2 if self.width() >= 1180 else 1
        self.grid_layout.setColumnStretch(0, 1)
        self.grid_layout.setColumnStretch(1, 1 if cols == 2 else 0)
        for i, app in enumerate(apps):
            tile = AppTile(app.package, app.name, app.icon_path)
            tile.launched.connect(self._launch)
            tile.removed.connect(self._remove)
            self.grid_layout.addWidget(tile, i // cols, i % cols)
        self.grid_layout.setRowStretch(self.grid_layout.rowCount(), 1)

    def _launch(self, package: str):
        try:
            self.backend.launch_app(package)
        except BackendError as e:
            self._error(str(e))

    def _remove(self, package: str):
        if QMessageBox.question(
            self, "卸载", f"确定要卸载 {package} 吗？",
            QMessageBox.Yes | QMessageBox.No,
        ) == QMessageBox.Yes:
            try:
                self.backend.remove_app(package)
            except Exception as e:  # noqa: BLE001
                self._error(str(e))
            self._refresh()

    def _error(self, msg: str):
        QMessageBox.warning(self, "提示", msg)
