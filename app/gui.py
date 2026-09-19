"""PyQt5 desktop interface for both georeferencing workflows."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QFont
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from rasterreg import (
    GeoreferencerError,
    RegistrationConfig,
    SatelliteSceneConfig,
    georeference,
    process_satellite_scene,
)
from rasterreg.scene import discover_scene

LOGGER = logging.getLogger(__name__)
RASTERS = "Raster images (*.tif *.tiff *.png *.jpg *.jpeg);;All files (*)"


class WorkflowWorker(QThread):
    """Run either workflow without blocking Qt."""

    stage = pyqtSignal(str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, workflow: str, values: dict[str, Any]) -> None:
        super().__init__()
        self.workflow, self.values = workflow, values

    def run(self) -> None:
        try:
            if self.workflow == "register":
                self.stage.emit("Extracting features and estimating alignment")
                result = georeference(**self.values)
            else:
                result = process_satellite_scene(**self.values, status=self.stage.emit)
        except (GeoreferencerError, OSError, ValueError) as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # GUI boundary
            LOGGER.exception("Unexpected workflow failure")
            self.failed.emit(f"Unexpected processing error: {exc}")
        else:
            self.succeeded.emit(result)


class MainWindow(QMainWindow):
    """Desktop front end for raster registration and RPC/DEM processing."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Raster Registration Toolkit")
        self.setMinimumSize(900, 700)
        self.resize(1040, 760)
        self.worker: WorkflowWorker | None = None
        self._build_ui()

    @staticmethod
    def _path_row(field: QLineEdit, button: QPushButton) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(field, 1)
        layout.addWidget(button)
        return widget

    def _browse_file(self, field: QLineEdit, title: str, save: bool = False) -> None:
        chooser = QFileDialog.getSaveFileName if save else QFileDialog.getOpenFileName
        path, _ = chooser(self, title, filter=RASTERS)
        if path:
            field.setText(path)

    def _browse_directory(self, field: QLineEdit, title: str) -> None:
        path = QFileDialog.getExistingDirectory(self, title)
        if path:
            field.setText(path)

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(30, 26, 30, 26)
        root.setSpacing(16)
        title = QLabel("Raster Registration Toolkit")
        font = QFont(title.font())
        font.setPointSize(font.pointSize() + 8)
        font.setBold(True)
        title.setFont(font)
        subtitle = QLabel("Feature-based alignment and RPC/DEM orthorectification")
        subtitle.setObjectName("subtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._registration_tab(), "Raster Registration")
        self.tabs.addTab(self._satellite_tab(), "Satellite Scene (RPC / DEM)")
        root.addWidget(self.tabs, 1)

        status_box = QFrame()
        status_box.setObjectName("statusBox")
        status_layout = QVBoxLayout(status_box)
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Processing stages and output details appear here.")
        self.details.setMaximumHeight(135)
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress)
        status_layout.addWidget(self.details)
        root.addWidget(status_box)
        self.setCentralWidget(central)
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #f5f7fb; color: #172033; }
            QLabel#subtitle { color: #61708a; font-size: 14px; }
            QTabWidget::pane { border: 1px solid #d8dfeb; background: white; border-radius: 8px; }
            QTabBar::tab { padding: 11px 22px; margin-right: 4px; }
            QTabBar::tab:selected { color: #2457d6; border-bottom: 3px solid #2457d6; }
            QGroupBox { font-weight: 600; border: 1px solid #dce2ec; border-radius: 7px;
                        margin-top: 12px; padding: 15px 10px 8px; background: white; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
            QLineEdit, QComboBox, QPlainTextEdit { background: white; border: 1px solid #cdd6e4;
                        border-radius: 5px; padding: 7px; }
            QPushButton { background: #edf1f7; border: 1px solid #cbd4e2; border-radius: 5px;
                          padding: 8px 15px; }
            QPushButton#primary { background: #2457d6; color: white; border: none;
                                  font-weight: 600; }
            QPushButton:disabled { color: #99a3b4; background: #e8ebf0; }
            QFrame#statusBox { background: white; border: 1px solid #dce2ec; border-radius: 8px; }
            QLabel#statusLabel { color: #2457d6; font-weight: 600; }
        """)

    def _registration_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 20, 22, 20)
        inputs = QGroupBox("Input rasters")
        form = QFormLayout(inputs)
        self.source = QLineEdit()
        self.reference = QLineEdit()
        self.output = QLineEdit()
        for field, placeholder in (
            (self.source, "Raster to align"),
            (self.reference, "Georeferenced reference raster"),
            (self.output, "Output GeoTIFF"),
        ):
            field.setPlaceholderText(placeholder)
        b1 = QPushButton("Browse…")
        b1.clicked.connect(lambda: self._browse_file(self.source, "Source raster"))
        b2 = QPushButton("Browse…")
        b2.clicked.connect(lambda: self._browse_file(self.reference, "Reference raster"))
        b3 = QPushButton("Browse…")
        b3.clicked.connect(lambda: self._browse_file(self.output, "Output GeoTIFF", True))
        form.addRow("Source", self._path_row(self.source, b1))
        form.addRow("Reference", self._path_row(self.reference, b2))
        form.addRow("Output", self._path_row(self.output, b3))
        layout.addWidget(inputs)
        options = QGroupBox("Options")
        opts = QGridLayout(options)
        self.rotation = QComboBox()
        for degrees in (0, 90, 180, 270):
            self.rotation.addItem(f"{degrees}°", degrees)
        self.rotation.setCurrentIndex(2)
        self.alpha = QCheckBox("Add alpha band")
        self.reg_overwrite = QCheckBox("Overwrite existing output")
        opts.addWidget(QLabel("Source rotation"), 0, 0)
        opts.addWidget(self.rotation, 0, 1)
        opts.addWidget(self.alpha, 1, 0)
        opts.addWidget(self.reg_overwrite, 1, 1)
        layout.addWidget(options)
        row = QHBoxLayout()
        row.addStretch()
        self.register_button = QPushButton("Run Registration")
        self.register_button.setObjectName("primary")
        self.register_button.clicked.connect(self.start_registration)
        row.addWidget(self.register_button)
        layout.addLayout(row)
        layout.addStretch()
        return page

    def _satellite_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 20, 22, 20)
        inputs = QGroupBox("Scene inputs")
        form = QFormLayout(inputs)
        self.scene_dir = QLineEdit()
        self.dem = QLineEdit()
        self.scene_output = QLineEdit()
        self.scene_reference = QLineEdit()
        fields = [
            (self.scene_dir, "Folder containing TIFF imagery and RPC XML"),
            (self.dem, "Elevation raster"),
            (self.scene_output, "Folder for registered.tif and reports"),
            (self.scene_reference, "Optional reference for feature refinement"),
        ]
        for field, placeholder in fields:
            field.setPlaceholderText(placeholder)
        for label, field, directory in (
            ("Scene folder", self.scene_dir, True),
            ("DEM raster", self.dem, False),
            ("Output folder", self.scene_output, True),
            ("Reference", self.scene_reference, False),
        ):
            button = QPushButton("Browse…")
            if directory:
                button.clicked.connect(
                    lambda _, f=field, label_name=label: self._browse_directory(f, label_name)
                )
            else:
                button.clicked.connect(
                    lambda _, f=field, label_name=label: self._browse_file(f, label_name)
                )
            form.addRow(label, self._path_row(field, button))
        layout.addWidget(inputs)
        options = QGroupBox("Processing options")
        grid = QGridLayout(options)
        self.use_dem = QCheckBox("Use terrain correction")
        self.use_dem.setChecked(True)
        self.refine = QCheckBox("Enable feature refinement")
        self.scene_overwrite = QCheckBox("Overwrite outputs")
        self.resolution = QLineEdit("10")
        self.output_crs = QLineEdit("EPSG:4326")
        grid.addWidget(self.use_dem, 0, 0)
        grid.addWidget(self.refine, 0, 1)
        grid.addWidget(self.scene_overwrite, 0, 2)
        grid.addWidget(QLabel("Resolution (meters)"), 1, 0)
        grid.addWidget(self.resolution, 1, 1)
        grid.addWidget(QLabel("Output CRS"), 2, 0)
        grid.addWidget(self.output_crs, 2, 1)
        layout.addWidget(options)
        row = QHBoxLayout()
        self.inspect_button = QPushButton("Inspect Scene")
        self.inspect_button.clicked.connect(self.inspect_scene)
        self.scene_button = QPushButton("Process Satellite Scene")
        self.scene_button.setObjectName("primary")
        self.scene_button.clicked.connect(self.start_scene)
        row.addStretch()
        row.addWidget(self.inspect_button)
        row.addWidget(self.scene_button)
        layout.addLayout(row)
        layout.addStretch()
        return page

    def inspect_scene(self) -> None:
        try:
            scene = discover_scene(self.scene_dir.text().strip())
        except (GeoreferencerError, OSError, ValueError) as exc:
            self._fail(str(exc))
            return
        lines = [
            "Scene inspection complete",
            f"Primary raster: {scene.image}",
            f"RPC metadata: {scene.rpc}",
        ]
        lines.append(f"Panchromatic raster: {scene.panchromatic_image or 'not discovered'}")
        lines.append(f"Reference raster: {scene.reference or 'not discovered'}")
        self.status_label.setText("Scene inputs discovered")
        self.details.setPlainText("\n".join(lines))

    def start_registration(self) -> None:
        if not all(field.text().strip() for field in (self.source, self.reference, self.output)):
            self._fail("Select source, reference, and output rasters.")
            return
        self._start(
            "register",
            {
                "source_path": Path(self.source.text()),
                "reference_path": Path(self.reference.text()),
                "output_path": Path(self.output.text()),
                "config": RegistrationConfig(
                    source_rotation_degrees=int(self.rotation.currentData()),
                    add_alpha=self.alpha.isChecked(),
                    overwrite=self.reg_overwrite.isChecked(),
                ),
            },
        )

    def start_scene(self) -> None:
        if not self.scene_dir.text().strip() or not self.scene_output.text().strip():
            self._fail("Select a scene folder and output folder.")
            return
        if self.use_dem.isChecked() and not self.dem.text().strip():
            self._fail("Select a DEM or disable terrain correction.")
            return
        try:
            resolution = float(self.resolution.text())
        except ValueError:
            self._fail("Resolution must be a number in meters.")
            return
        reference = self.scene_reference.text().strip() or None
        self._start(
            "scene",
            {
                "scene_directory": Path(self.scene_dir.text()),
                "dem_path": Path(self.dem.text()) if self.dem.text().strip() else None,
                "output_directory": Path(self.scene_output.text()),
                "reference_path": Path(reference) if reference else None,
                "config": SatelliteSceneConfig(
                    output_crs=self.output_crs.text().strip(),
                    resolution_meters=resolution,
                    use_dem=self.use_dem.isChecked(),
                    refine_features=self.refine.isChecked(),
                    overwrite=self.scene_overwrite.isChecked(),
                ),
            },
        )

    def _start(self, workflow: str, values: dict[str, Any]) -> None:
        self.details.clear()
        self._set_running(True)
        self.worker = WorkflowWorker(workflow, values)
        self.worker.stage.connect(self._stage)
        self.worker.succeeded.connect(self._complete)
        self.worker.failed.connect(self._fail)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _stage(self, message: str) -> None:
        self.status_label.setText(message)
        self.details.appendPlainText(message)

    def _complete(self, result: Any) -> None:
        self.status_label.setText("Processing completed")
        lines = ["Completed successfully", f"Output: {result.output_path}"]
        if hasattr(result, "alignment"):
            lines += [
                f"Retained matches: {result.alignment.match_count}",
                f"RANSAC inliers: {result.alignment.inlier_count}",
            ]
        else:
            lines += [f"Metadata: {result.metadata_path}", f"Footprint: {result.footprint_path}"]
        self.details.setPlainText("\n".join(lines))

    def _fail(self, message: str) -> None:
        self.status_label.setText("Action could not be completed")
        self.details.setPlainText(message)
        QMessageBox.critical(self, "Raster Registration Toolkit", message)

    def _set_running(self, running: bool) -> None:
        self.tabs.setEnabled(not running)
        self.register_button.setEnabled(not running)
        self.scene_button.setEnabled(not running)
        self.inspect_button.setEnabled(not running)
        self.progress.setVisible(running)
        if running:
            self.status_label.setText("Starting workflow…")

    def _finished(self) -> None:
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        self._set_running(False)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.worker and self.worker.isRunning():
            QMessageBox.information(
                self, "Processing in progress", "Wait for the current workflow to finish."
            )
            event.ignore()
        else:
            event.accept()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
