"""PyQt6 system tray / menu bar application for leafpress."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


def _open_file(path: Path) -> None:
    """Open a file with the system default application."""
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", str(path)], check=False)
    elif system == "Windows":
        subprocess.run(["start", "", str(path)], shell=True, check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def _make_tray_icon() -> QIcon:
    """Create a simple document icon for the system tray / menu bar."""
    px = QPixmap(32, 32)
    px.fill(QColor(0, 0, 0, 0))
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#1a73e8"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(4, 2, 24, 28, 4, 4)
    p.setPen(QColor("white"))
    font = p.font()
    font.setPointSize(13)
    font.setBold(True)
    p.setFont(font)
    p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "D")
    p.end()
    return QIcon(px)


class ConvertWorker(QThread):
    """Runs the leafpress conversion pipeline in a background thread."""

    log = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(
        self,
        source: str,
        output_dir: Path,
        fmt: str,
        config_path: Path | None,
        cover_page: bool,
        include_toc: bool,
        open_after: bool = False,
    ) -> None:
        super().__init__()
        self._source = source
        self._output_dir = output_dir
        self._fmt = fmt
        self._config_path = config_path
        self._cover_page = cover_page
        self._include_toc = include_toc
        self._open_after = open_after

    def run(self) -> None:
        try:
            from leafpress.pipeline import convert

            self.log.emit(f"Converting {self._source!r} to {self._fmt.upper()}...")
            files = convert(
                source=self._source,
                output_dir=self._output_dir,
                format=self._fmt,
                config_path=self._config_path,
                cover_page=self._cover_page,
                include_toc=self._include_toc,
            )
            names = "\n".join(str(f) for f in files)
            self.log.emit(f"Done!\n{names}")
            if self._open_after:
                for f in files:
                    _open_file(f)
            self.finished.emit(True, f"Generated {len(files)} file(s).")
        except Exception as exc:
            self.log.emit(f"Error: {exc}")
            self.finished.emit(False, str(exc))


class LeafpressWindow(QMainWindow):
    """Main conversion window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("leafpress")
        self.setMinimumWidth(540)
        self._worker: ConvertWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        form = QFormLayout()
        form.setSpacing(8)

        # Source
        src_row = QHBoxLayout()
        self._source = QLineEdit()
        self._source.setPlaceholderText("/path/to/project  or  https://github.com/org/repo")
        src_btn = self._browse_btn(self._browse_source)
        src_row.addWidget(self._source)
        src_row.addWidget(src_btn)
        form.addRow("Source:", src_row)

        # Output directory
        out_row = QHBoxLayout()
        self._output = QLineEdit("output")
        out_btn = self._browse_btn(self._browse_output)
        out_row.addWidget(self._output)
        out_row.addWidget(out_btn)
        form.addRow("Output dir:", out_row)

        # Format
        self._format = QComboBox()
        self._format.addItems(["pdf", "docx", "both"])
        form.addRow("Format:", self._format)

        # Branding config (optional)
        cfg_row = QHBoxLayout()
        self._config = QLineEdit()
        self._config.setPlaceholderText("Optional: path to leafpress.yml branding config")
        cfg_btn = self._browse_btn(self._browse_config)
        cfg_row.addWidget(self._config)
        cfg_row.addWidget(cfg_btn)
        form.addRow("Branding config:", cfg_row)

        root.addLayout(form)

        # Options checkboxes
        opts = QHBoxLayout()
        self._cover = QCheckBox("Cover page")
        self._cover.setChecked(True)
        self._toc = QCheckBox("Table of contents")
        self._toc.setChecked(True)
        self._open_after = QCheckBox("Open after conversion")
        opts.addWidget(self._cover)
        opts.addWidget(self._toc)
        opts.addWidget(self._open_after)
        opts.addStretch()
        root.addLayout(opts)

        # Convert button + indeterminate progress bar
        btn_row = QHBoxLayout()
        self._convert_btn = QPushButton("Convert")
        self._convert_btn.setFixedHeight(36)
        self._convert_btn.clicked.connect(self._run_convert)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate spinner
        self._progress.setVisible(False)
        self._progress.setFixedHeight(36)
        btn_row.addWidget(self._convert_btn)
        btn_row.addWidget(self._progress)
        root.addLayout(btn_row)

        # Log output
        root.addWidget(QLabel("Log:"))
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(160)
        self._log.setPlaceholderText("Conversion output will appear here...")
        root.addWidget(self._log)

    @staticmethod
    def _browse_btn(slot: object) -> QPushButton:
        btn = QPushButton("Browse...")
        btn.setFixedWidth(80)
        btn.clicked.connect(slot)  # type: ignore[arg-type]
        return btn

    # --- file dialogs ---

    def _browse_source(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select MkDocs project folder")
        if d:
            self._source.setText(d)

    def _browse_output(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select output folder")
        if d:
            self._output.setText(d)

    def _browse_config(self) -> None:
        f, _ = QFileDialog.getOpenFileName(
            self, "Select branding config", filter="YAML files (*.yml *.yaml)"
        )
        if f:
            self._config.setText(f)

    # --- conversion ---

    def _run_convert(self) -> None:
        source = self._source.text().strip()
        if not source:
            QMessageBox.warning(self, "leafpress", "Please specify a source path or URL.")
            return

        config_text = self._config.text().strip()
        config_path = Path(config_text) if config_text else None

        self._convert_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._log.clear()

        self._worker = ConvertWorker(
            source=source,
            output_dir=Path(self._output.text() or "output"),
            fmt=self._format.currentText(),
            config_path=config_path,
            cover_page=self._cover.isChecked(),
            include_toc=self._toc.isChecked(),
            open_after=self._open_after.isChecked(),
        )
        self._worker.log.connect(self._log.append)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self, success: bool, message: str) -> None:
        self._convert_btn.setEnabled(True)
        self._progress.setVisible(False)
        if success:
            QMessageBox.information(self, "leafpress", message)
        else:
            QMessageBox.critical(self, "leafpress -- Error", message)


class LeafpressTray(QSystemTrayIcon):
    """System tray / menu bar icon with right-click menu."""

    def __init__(self, app: QApplication) -> None:
        super().__init__(_make_tray_icon(), app)
        self._window = LeafpressWindow()
        self.setToolTip("leafpress")
        self._build_menu()
        self.activated.connect(self._on_activated)

    def _build_menu(self) -> None:
        menu = QMenu()
        open_action = QAction("Open leafpress", menu)
        open_action.triggered.connect(self._show_window)
        menu.addAction(open_action)
        menu.addSeparator()
        quit_action = QAction("Quit leafpress", menu)
        quit_action.triggered.connect(QApplication.instance().quit)  # type: ignore[union-attr]
        menu.addAction(quit_action)
        self.setContextMenu(menu)

    def _show_window(self) -> None:
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._show_window()


def _hide_dock_icon_macos() -> None:
    """On macOS, set the activation policy so the app does not appear in the Dock."""
    if sys.platform != "darwin":
        return
    try:
        from AppKit import NSApp, NSApplicationActivationPolicyAccessory  # type: ignore[import]

        NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    except ImportError:
        pass  # pyobjc not installed; dock icon will be visible until packaged


def run_ui(show: bool = False) -> None:
    """Launch the leafpress menu bar / system tray application."""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # stay alive when the window is closed
    app.setApplicationName("leafpress")
    _hide_dock_icon_macos()  # must run after QApplication initialises NSApplication

    if not QSystemTrayIcon.isSystemTrayAvailable():
        from leafpress.exceptions import LeafpressError

        raise LeafpressError(
            "System tray is not available on this platform. "
            "On macOS, ensure you are running a graphical session."
        )

    tray = LeafpressTray(app)
    tray.show()
    if show:
        tray._show_window()
    tray.showMessage(
        "leafpress",
        "leafpress is running in the menu bar.",
        QSystemTrayIcon.MessageIcon.Information,
        2000,
    )
    sys.exit(app.exec())
