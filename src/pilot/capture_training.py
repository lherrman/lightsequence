"""Capture labelled Traktor timeline screenshots for training data.

Usage:
  1. Run the script with uv run src/pilot/capture_training.py.
  2. Click "Select Deck Region" and drag the rectangle over the timeline.
  3. Press "Save Bass" or "Save Breakdown" (or use keyboard shortcuts 'B'/'D').
     Each press grabs the region, writes a PNG into the respective folder,
     and logs how long the capture took.

The default output directory is ./captures/{bass,breakdown}. Change it via the
"Change Output Folder" button before capturing.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from mss import mss
from mss import tools
from PySide6.QtCore import QEventLoop, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QGuiApplication, QKeySequence, QPainter, QColor, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
    QRubberBand,
)


@dataclass
class CaptureRegion:
    rect: QRect

    def summary(self) -> str:
        return (
            f"x={self.rect.x()} y={self.rect.y()} "
            f"w={self.rect.width()} h={self.rect.height()}"
        )


class RegionOverlay(QWidget):
    """Full-screen overlay to drag-select a rectangle."""

    region_selected = Signal(QRect)
    selection_cancelled = Signal()

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowState(Qt.WindowFullScreen)
        self.setCursor(Qt.CrossCursor)

        geometry = QRect()
        for screen in QGuiApplication.screens():
            geometry = geometry.united(screen.geometry())
        self.setGeometry(geometry)

        self._rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self._origin = QPoint()
        self._current = QPoint()

    def paintEvent(self, event) -> None:  # noqa: D401 - Qt override
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        painter.end()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        self._origin = event.globalPosition().toPoint()
        self._current = self._origin
        self._rubber_band.setGeometry(QRect(self._origin, QSize(0, 0)))
        self._rubber_band.show()

    def mouseMoveEvent(self, event) -> None:
        if not self._rubber_band.isVisible():
            return
        self._current = event.globalPosition().toPoint()
        rect = QRect(self._origin, self._current).normalized()
        self._rubber_band.setGeometry(rect)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.LeftButton or not self._rubber_band.isVisible():
            return
        self._rubber_band.hide()
        rect = QRect(self._origin, event.globalPosition().toPoint()).normalized()
        if rect.width() < 5 or rect.height() < 5:
            self.selection_cancelled.emit()
        else:
            self.region_selected.emit(rect)
        self.close()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self._rubber_band.hide()
            self.selection_cancelled.emit()
            self.close()


class TrainingCaptureWindow(QMainWindow):
    """GUI to capture labelled screenshots for training."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Timeline Training Capture")
        self.resize(520, 420)

        self.region: Optional[CaptureRegion] = None
        self.base_dir = Path.cwd() / "captures"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.counts = {"bass": 0, "breakdown": 0}

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setSpacing(8)

        self.instructions = QLabel(
            "1. Select the deck/timeline region.\n"
            "2. Use the Bass or Breakdown buttons (or B/D keys) to save captures."
        )
        layout.addWidget(self.instructions)

        select_btn = QPushButton("Select Deck Region")
        select_btn.clicked.connect(self._select_region)
        layout.addWidget(select_btn)

        dir_row = QVBoxLayout()
        self.dir_edit = QLineEdit(str(self.base_dir))
        self.dir_edit.setReadOnly(True)
        change_dir = QPushButton("Change Output Folder…")
        change_dir.clicked.connect(self._change_output_dir)
        dir_row.addWidget(self.dir_edit)
        dir_row.addWidget(change_dir)
        dir_widget = QWidget()
        dir_widget.setLayout(dir_row)
        layout.addWidget(dir_widget)

        bass_btn = QPushButton("Save Bass (B)")
        bass_btn.clicked.connect(lambda: self._capture_and_save("bass"))
        layout.addWidget(bass_btn)

        breakdown_btn = QPushButton("Save Breakdown (D)")
        breakdown_btn.clicked.connect(lambda: self._capture_and_save("breakdown"))
        layout.addWidget(breakdown_btn)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, stretch=1)

        self.status = QLabel("No region selected.")
        layout.addWidget(self.status)

        self.setCentralWidget(container)

        QShortcut(QKeySequence("B"), self, activated=lambda: self._capture_and_save("bass"))
        QShortcut(QKeySequence("D"), self, activated=lambda: self._capture_and_save("breakdown"))
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self._select_region)

    # region selection -------------------------------------------------
    def _select_region(self) -> None:
        rect = self._grab_region()
        if rect is None:
            self._append_log("Region selection cancelled.")
            return
        self.region = CaptureRegion(rect)
        self._append_log(f"Region set: {self.region.summary()}")
        self._update_status()

    def _grab_region(self) -> Optional[QRect]:
        overlay = RegionOverlay()
        loop = QEventLoop()
        selected: dict[str, Optional[QRect]] = {"rect": None}

        overlay.region_selected.connect(lambda rect: self._finish_region(loop, selected, rect))
        overlay.selection_cancelled.connect(loop.quit)
        overlay.show()
        loop.exec()
        overlay.deleteLater()
        return selected["rect"]

    def _finish_region(
        self,
        loop: QEventLoop,
        result: dict[str, Optional[QRect]],
        rect: QRect,
    ) -> None:
        result["rect"] = rect
        loop.quit()

    def _change_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choose Output Folder", str(self.base_dir))
        if directory:
            self.base_dir = Path(directory)
            self.base_dir.mkdir(parents=True, exist_ok=True)
            self.dir_edit.setText(str(self.base_dir))
            self._append_log(f"Output folder set to: {self.base_dir}")

    def _update_status(self) -> None:
        region_text = self.region.summary() if self.region else "No region"
        counts_text = ", ".join(f"{label}: {count}" for label, count in self.counts.items())
        self.status.setText(f"Region: {region_text} | Captures -> {counts_text}")

    # capture -----------------------------------------------------------
    def _capture_and_save(self, label: str) -> None:
        if not self.region:
            self._append_log("Select a region before capturing.")
            return

        target_dir = self.base_dir / label
        target_dir.mkdir(parents=True, exist_ok=True)

        rect = self.region.rect
        bbox = {
            "left": rect.x(),
            "top": rect.y(),
            "width": rect.width(),
            "height": rect.height(),
        }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{label}_{timestamp}.png"
        filepath = target_dir / filename

        start = time.perf_counter()
        with mss() as grabber:
            shot = grabber.grab(bbox)
            tools.to_png(shot.rgb, shot.size, output=str(filepath))
        elapsed = time.perf_counter() - start

        self.counts[label] += 1
        self._append_log(
            f"Saved {label} capture -> {filepath} ({elapsed * 1000:.2f} ms)"
        )
        self._update_status()

    # logging ----------------------------------------------------------
    def _append_log(self, message: str) -> None:
        self.log.appendPlainText(message)
        scrollbar = self.log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


def main() -> None:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    window = TrainingCaptureWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
