"""PyQt6 system tray / menu bar application for leafpress."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QByteArray, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PyQt6.QtSvg import QSvgRenderer
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


_LOGO_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <rect width="100" height="100" rx="20" fill="#2e7d32"/>
  <rect x="22" y="18" width="42" height="54" rx="5" fill="white"/>
  <path d="M 50 18 L 64 32 H 50 Z" fill="#a5d6a7"/>
  <rect x="30" y="40" width="24" height="4" rx="2" fill="#c8e6c9"/>
  <rect x="30" y="50" width="18" height="4" rx="2" fill="#c8e6c9"/>
  <g transform="translate(52, 42)">
    <path d="M 0 38 C 0 18, 14 4, 36 0 C 32 8, 26 16, 26 28 C 26 32, 24 36, 20 38 Z"
          fill="#66bb6a" opacity="0.95"/>
    <path d="M 2 36 C 10 26, 20 14, 34 2"
          stroke="white" stroke-width="2" fill="none" opacity="0.6"/>
    <path d="M 12 36 C 16 28, 22 20, 30 10"
          stroke="white" stroke-width="1.2" fill="none" opacity="0.4"/>
    <path d="M 6 28 C 10 24, 16 18, 22 12"
          stroke="white" stroke-width="1.2" fill="none" opacity="0.4"/>
  </g>
</svg>
"""


def _make_tray_icon(size: int = 32) -> QIcon:
    """Render the leafpress logo SVG as an icon at the given size."""
    renderer = QSvgRenderer(QByteArray(_LOGO_SVG.encode()))
    px = QPixmap(size, size)
    px.fill(QColor(0, 0, 0, 0))
    p = QPainter(px)
    renderer.render(p)
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
        local_time: bool = False,
    ) -> None:
        super().__init__()
        self._source = source
        self._output_dir = output_dir
        self._fmt = fmt
        self._config_path = config_path
        self._cover_page = cover_page
        self._include_toc = include_toc
        self._open_after = open_after
        self._local_time = local_time

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
                local_time=self._local_time,
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
        self.setWindowTitle("leafpress — Convert")
        self.setWindowIcon(_make_tray_icon())
        self.setMinimumWidth(540)
        self._worker: ConvertWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        # Header with icon
        header = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(_make_tray_icon().pixmap(24, 24))
        title_label = QLabel("leafpress \u2014 Convert")
        font = title_label.font()
        font.setPointSize(16)
        font.setBold(True)
        title_label.setFont(font)
        header.addWidget(icon_label)
        header.addWidget(title_label)
        header.addStretch()
        root.addLayout(header)

        form = QFormLayout()
        form.setSpacing(8)

        # Source
        src_row = QHBoxLayout()
        self._source = QLineEdit()
        self._source.setPlaceholderText("/path/to/project  or  https://github.com/org/repo")
        self._source.setToolTip("Local path to an MkDocs project or a git URL")
        src_btn = self._browse_btn(self._browse_source, tooltip="\u2318O")
        src_row.addWidget(self._source)
        src_row.addWidget(src_btn)
        form.addRow("Source:", src_row)

        # Output directory
        out_row = QHBoxLayout()
        self._output = QLineEdit("output")
        self._output.setToolTip("Directory where output files will be saved")
        out_btn = self._browse_btn(self._browse_output)
        out_row.addWidget(self._output)
        out_row.addWidget(out_btn)
        form.addRow("Output dir:", out_row)

        # Format
        self._format = QComboBox()
        self._format.addItems(["pdf", "docx", "html", "odt", "epub", "markdown", "both", "all"])
        self._format.setToolTip("'both' = PDF + DOCX, 'all' = every format")
        form.addRow("Format:", self._format)

        # Branding config (optional)
        cfg_row = QHBoxLayout()
        self._config = QLineEdit()
        self._config.setPlaceholderText("Optional: path to leafpress.yml branding config")
        self._config.setToolTip("YAML file with company name, logo, colors, and footer options")
        cfg_btn = self._browse_btn(self._browse_config)
        cfg_row.addWidget(self._config)
        cfg_row.addWidget(cfg_btn)
        form.addRow("Branding config:", cfg_row)

        root.addLayout(form)

        # Options checkboxes
        opts = QHBoxLayout()
        self._cover = QCheckBox("Cover page")
        self._cover.setChecked(True)
        self._cover.setToolTip("Add a branded cover page with title, author, and version")
        self._toc = QCheckBox("Table of contents")
        self._toc.setChecked(True)
        self._toc.setToolTip("Generate a table of contents from page headings")
        self._open_after = QCheckBox("Open after conversion")
        self._open_after.setToolTip("Open generated files with the default application")
        self._local_time = QCheckBox("Use local timezone for dates")
        self._local_time.setToolTip("Show dates in local time instead of UTC")
        opts.addWidget(self._cover)
        opts.addWidget(self._toc)
        opts.addWidget(self._open_after)
        opts.addWidget(self._local_time)
        opts.addStretch()
        root.addLayout(opts)

        # Convert button + indeterminate progress bar
        btn_row = QHBoxLayout()
        self._convert_btn = QPushButton("Convert  \u2318\u23ce")
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

        # Keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self._browse_source)
        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self._run_convert)

    @staticmethod
    def _browse_btn(slot: object, tooltip: str = "") -> QPushButton:
        btn = QPushButton("Browse\u2026")
        btn.setFixedWidth(80)
        btn.clicked.connect(slot)  # type: ignore[arg-type]
        if tooltip:
            btn.setToolTip(tooltip)
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
            local_time=self._local_time.isChecked(),
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


class ImportWorker(QThread):
    """Runs a document import in a background thread."""

    log = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(
        self,
        files: list[Path],
        output_dir: Path | None,
        extract_images: bool,
        include_notes: bool,
        open_after: bool = False,
    ) -> None:
        super().__init__()
        self._files = files
        self._output_dir = output_dir
        self._extract_images = extract_images
        self._include_notes = include_notes
        self._open_after = open_after

    def run(self) -> None:
        try:
            results: list[Path] = []
            for file in self._files:
                suffix = file.suffix.lower()
                self.log.emit(f"Importing {file.name}...")
                if suffix == ".docx":
                    from leafpress.importer.converter import import_docx

                    r = import_docx(
                        docx_path=file,
                        output_path=self._output_dir,
                        extract_images=self._extract_images,
                    )
                elif suffix == ".pptx":
                    from leafpress.importer.converter_pptx import import_pptx

                    r = import_pptx(
                        pptx_path=file,
                        output_path=self._output_dir,
                        extract_images=self._extract_images,
                        include_notes=self._include_notes,
                    )
                elif suffix == ".xlsx":
                    from leafpress.importer.converter_xlsx import import_xlsx

                    r = import_xlsx(
                        xlsx_path=file,
                        output_path=self._output_dir,
                    )
                elif suffix == ".tex":
                    from leafpress.importer.converter_tex import import_tex

                    r = import_tex(
                        tex_path=file,
                        output_path=self._output_dir,
                        extract_images=self._extract_images,
                    )
                else:
                    self.log.emit(f"  Skipped (unsupported: {suffix})")
                    continue
                results.append(r.markdown_path)
                self.log.emit(f"  -> {r.markdown_path}")
                if r.warnings:
                    for w in r.warnings:
                        self.log.emit(f"  Warning: {w}")

            names = "\n".join(str(p) for p in results)
            self.log.emit(f"Done!\n{names}")
            if self._open_after:
                for p in results:
                    _open_file(p)
            self.finished.emit(True, f"Imported {len(results)} file(s).")
        except Exception as exc:
            self.log.emit(f"Error: {exc}")
            self.finished.emit(False, str(exc))


class ImportWindow(QMainWindow):
    """Document import window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("leafpress — Import")
        self.setWindowIcon(_make_tray_icon())
        self.setMinimumWidth(540)
        self._worker: ImportWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        # Header with icon
        header = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(_make_tray_icon().pixmap(24, 24))
        title_label = QLabel("leafpress \u2014 Import")
        font = title_label.font()
        font.setPointSize(16)
        font.setBold(True)
        title_label.setFont(font)
        header.addWidget(icon_label)
        header.addWidget(title_label)
        header.addStretch()
        root.addLayout(header)

        form = QFormLayout()
        form.setSpacing(8)

        # Files
        files_row = QHBoxLayout()
        self._files = QLineEdit()
        self._files.setPlaceholderText("Select .docx, .pptx, .xlsx, or .tex files")
        self._files.setReadOnly(True)
        files_btn = QPushButton("Browse\u2026")
        files_btn.setFixedWidth(80)
        files_btn.setToolTip("\u2318O")
        files_btn.clicked.connect(self._browse_files)
        files_row.addWidget(self._files)
        files_row.addWidget(files_btn)
        form.addRow("Files:", files_row)

        # Output directory
        out_row = QHBoxLayout()
        self._output = QLineEdit()
        self._output.setPlaceholderText("Same directory as source files")
        self._output.setToolTip("Leave blank to save next to the source files")
        out_btn = QPushButton("Browse\u2026")
        out_btn.setFixedWidth(80)
        out_btn.clicked.connect(self._browse_output)
        out_row.addWidget(self._output)
        out_row.addWidget(out_btn)
        form.addRow("Output dir:", out_row)

        root.addLayout(form)

        # Options
        opts = QHBoxLayout()
        self._extract_images = QCheckBox("Extract images")
        self._extract_images.setChecked(True)
        self._extract_images.setToolTip("Save embedded images to an assets/ directory")
        self._include_notes = QCheckBox("Include speaker notes (PPTX)")
        self._include_notes.setChecked(True)
        self._include_notes.setToolTip("Add speaker notes as blockquotes beneath each slide")
        self._open_after = QCheckBox("Open after import")
        self._open_after.setToolTip("Open generated Markdown files with the default application")
        opts.addWidget(self._extract_images)
        opts.addWidget(self._include_notes)
        opts.addWidget(self._open_after)
        opts.addStretch()
        root.addLayout(opts)

        # Import button + progress
        btn_row = QHBoxLayout()
        self._import_btn = QPushButton("Import  \u2318\u23ce")
        self._import_btn.setFixedHeight(36)
        self._import_btn.clicked.connect(self._run_import)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        self._progress.setFixedHeight(36)
        btn_row.addWidget(self._import_btn)
        btn_row.addWidget(self._progress)
        root.addLayout(btn_row)

        # Log
        root.addWidget(QLabel("Log:"))
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(160)
        self._log.setPlaceholderText("Import output will appear here...")
        root.addWidget(self._log)

        # Keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self._browse_files)
        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self._run_import)

        self._selected_files: list[Path] = []

    def _browse_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select documents to import",
            filter="Documents (*.docx *.pptx *.xlsx *.tex)",
        )
        if files:
            self._selected_files = [Path(f) for f in files]
            self._files.setText(", ".join(Path(f).name for f in files))

    def _browse_output(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select output folder")
        if d:
            self._output.setText(d)

    def _run_import(self) -> None:
        if not self._selected_files:
            QMessageBox.warning(self, "leafpress", "Please select files to import.")
            return

        output_text = self._output.text().strip()
        output_dir = Path(output_text) if output_text else None

        self._import_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._log.clear()

        self._worker = ImportWorker(
            files=self._selected_files,
            output_dir=output_dir,
            extract_images=self._extract_images.isChecked(),
            include_notes=self._include_notes.isChecked(),
            open_after=self._open_after.isChecked(),
        )
        self._worker.log.connect(self._log.append)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self, success: bool, message: str) -> None:
        self._import_btn.setEnabled(True)
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
        self._import_window = ImportWindow()
        self.setToolTip("leafpress")
        self._build_menu()
        self.activated.connect(self._on_activated)

    def _build_menu(self) -> None:
        menu = QMenu()
        open_action = QAction("Open leafpress", menu)
        open_action.triggered.connect(self._show_window)
        menu.addAction(open_action)
        import_action = QAction("Import files...", menu)
        import_action.triggered.connect(self._show_import)
        menu.addAction(import_action)
        menu.addSeparator()
        about_action = QAction("About leafpress", menu)
        about_action.triggered.connect(self._show_about)
        menu.addAction(about_action)
        menu.addSeparator()
        quit_action = QAction("Quit leafpress", menu)
        quit_action.triggered.connect(QApplication.instance().quit)  # type: ignore[union-attr]
        menu.addAction(quit_action)
        self.setContextMenu(menu)

    def _show_window(self) -> None:
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def _show_import(self) -> None:
        self._import_window.show()
        self._import_window.raise_()
        self._import_window.activateWindow()

    def _show_about(self) -> None:
        from leafpress import __version__

        release_url = f"https://github.com/hutchins/leafpress/releases/tag/v{__version__}"
        QMessageBox.about(
            self._window,
            "About leafpress",
            f"<h3>leafpress {__version__}</h3>"
            "<p>Convert MkDocs sites into branded PDF, DOCX, HTML, ODT, EPUB, "
            "and Markdown documents.</p>"
            "<p>Built by <b>Shane Hutchins</b></p>"
            '<p><a href="https://leafpress.dev">leafpress.dev</a> · '
            '<a href="https://github.com/hutchins/leafpress">GitHub</a> · '
            f'<a href="{release_url}">Release Notes</a></p>',
        )

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
