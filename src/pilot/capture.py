"""Interactive screen region capture tester using PySide6 and mss.

Select two regions (e.g. Traktor deck timelines) and press Enter to
capture them while measuring grab times. Use this as a prototype before
wiring the logic into the main application.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Optional

import mss
from PySide6.QtCore import QPoint, QRect, QSize, QEventLoop, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
    QRubberBand,
)


@dataclass
class CaptureRegion:
    name: str
    rect: QRect

    def summary(self) -> str:
        return (
            f"{self.name}: x={self.rect.x()} y={self.rect.y()} "
            f"w={self.rect.width()} h={self.rect.height()}"
        )


class RegionOverlay(QWidget):
    """Full-screen translucent overlay that lets the user drag out a rectangle."""

    region_selected = Signal(QRect)
    selection_cancelled = Signal()

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowState(Qt.WindowFullScreen)
        self.setCursor(Qt.CrossCursor)

        # Cover the union of all screens (supports multi-monitor setups).
        geometry = QRect()
        for screen in QGuiApplication.screens():
            geometry = geometry.united(screen.geometry())
        self.setGeometry(geometry)

        self._rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self._origin = QPoint()
        self._current = QPoint()

    # Basic translucent background for context.
    def paintEvent(self, event) -> None:  # noqa: D401 - Qt paint hook
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(self.rect(), QBrush(QColor(0, 0, 0, 120)))
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


class CaptureWindow(QMainWindow):
    """Simple controller for selecting and capturing two screen regions."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Capture Region Tester")
        self.resize(480, 360)

        self.deck_a: Optional[CaptureRegion] = None
        self.deck_b: Optional[CaptureRegion] = None

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setSpacing(8)

        self.info_label = QLabel(
            "Select the capture regions, then press Enter (or click Capture)\n"
            "Use 'Select Deck A/B' to re-define the rectangles."
        )
        layout.addWidget(self.info_label)

        select_a = QPushButton("Select Deck A Region")
        select_a.clicked.connect(lambda: self._choose_region("Deck A"))
        select_b = QPushButton("Select Deck B Region")
        select_b.clicked.connect(lambda: self._choose_region("Deck B"))

        capture_btn = QPushButton("Capture Now (Enter)")
        capture_btn.clicked.connect(self.capture)

        layout.addWidget(select_a)
        layout.addWidget(select_b)
        layout.addWidget(capture_btn)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, stretch=1)

        self.status = QLabel("No regions selected.")
        layout.addWidget(self.status)

        self.setCentralWidget(container)

    # region selection -------------------------------------------------
    def _choose_region(self, name: str) -> None:
        rect = self._grab_user_region()
        if rect is None:
            self._append_log(f"{name}: selection cancelled.")
            return
        region = CaptureRegion(name, rect)
        if name == "Deck A":
            self.deck_a = region
        else:
            self.deck_b = region
        self._append_log(f"{region.summary()}")
        self._update_status()

    def _grab_user_region(self) -> Optional[QRect]:
        overlay = RegionOverlay()
        loop = QEventLoop()
        result: dict[str, Optional[QRect]] = {"rect": None}

        def on_selected(rect: QRect) -> None:
            result["rect"] = rect
            loop.quit()

        def on_cancelled() -> None:
            loop.quit()

        overlay.region_selected.connect(on_selected)
        overlay.selection_cancelled.connect(on_cancelled)
        overlay.show()
        loop.exec()
        overlay.deleteLater()

        return result["rect"]

    def _update_status(self) -> None:
        parts = []
        if self.deck_a:
            parts.append(self.deck_a.summary())
        if self.deck_b:
            parts.append(self.deck_b.summary())
        self.status.setText(" | ".join(parts) if parts else "No regions selected.")

    # capture -----------------------------------------------------------
    def keyPressEvent(self, event) -> None:
        if event.key() in {Qt.Key_Return, Qt.Key_Enter}:
            self.capture()
        else:
            super().keyPressEvent(event)

    def capture(self) -> None:
        if not self.deck_a or not self.deck_b:
            self._append_log("Define both regions before capturing.")
            return

        regions = [self.deck_a, self.deck_b]
        total_start = time.perf_counter()
        durations: list[tuple[str, float]] = []

        with mss.mss() as grabber:
            for region in regions:
                rect = region.rect
                bbox = {
                    "left": rect.x(),
                    "top": rect.y(),
                    "width": rect.width(),
                    "height": rect.height(),
                }
                start = time.perf_counter()
                _ = grabber.grab(bbox)
                elapsed = time.perf_counter() - start
                durations.append((region.name, elapsed))

        total_elapsed = time.perf_counter() - total_start

        lines = [
            f"Captured {len(regions)} regions in {total_elapsed * 1000:.2f} ms",
            *[f"  {name}: {elapsed * 1000:.2f} ms" for name, elapsed in durations],
        ]
        self._append_log("\n".join(lines))

    # logging ----------------------------------------------------------
    def _append_log(self, message: str) -> None:
        self.log.appendPlainText(message)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())


def main() -> None:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    window = CaptureWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
