"""Fuente falsa: una imagen fija. Sirve para probar la app sin capturadora."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPixmap, QResizeEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from capturaia.capture.base import FrameSource


def demo_pattern(width: int = 1920, height: int = 1080) -> QImage:
    image = QImage(width, height, QImage.Format.Format_RGB888)
    painter = QPainter(image)
    gradient = QLinearGradient(0, 0, width, height)
    gradient.setColorAt(0, QColor("#1d2b53"))
    gradient.setColorAt(1, QColor("#7e2553"))
    painter.fillRect(image.rect(), gradient)
    bars = ["#ffffff", "#ffec27", "#29adff", "#00e436", "#ff77a8", "#ff004d", "#000000"]
    bar_w = width / len(bars)
    for i, color in enumerate(bars):
        painter.fillRect(QRectF(i * bar_w, height * 0.72, bar_w, height * 0.1), QColor(color))
    painter.setPen(QColor("white"))
    font = QFont()
    font.setPixelSize(max(24, height // 12))
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(
        QRectF(0, 0, width, height * 0.65),
        Qt.AlignmentFlag.AlignCenter,
        "CapturaIA\nImagen de prueba",
    )
    painter.end()
    return image


class _ScaledImageLabel(QLabel):
    def __init__(self, image: QImage) -> None:
        super().__init__()
        self._image = image
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(160, 90)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setStyleSheet("background: black;")

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        scaled = self._image.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(QPixmap.fromImage(scaled))


class ImageFileSource(FrameSource):
    def __init__(self, path: str = "") -> None:
        super().__init__()
        self._path = path
        self._image = QImage()
        self._label: _ScaledImageLabel | None = None

    def _load(self) -> QImage:
        if not self._path:
            return demo_pattern()
        image = QImage(str(Path(self._path).expanduser()))
        if image.isNull():
            self.error.emit(f"No se pudo abrir la imagen: {self._path}")
            return demo_pattern()
        return image

    def preview_widget(self) -> QWidget:
        if self._label is None:
            self._image = self._load()
            self._label = _ScaledImageLabel(self._image)
        return self._label

    def start(self) -> None:
        if self._image.isNull():
            self.preview_widget()
        name = Path(self._path).name if self._path else "imagen de prueba"
        self.status.emit(f"Imagen fija: {name} ({self._image.width()}x{self._image.height()})")

    def stop(self) -> None:
        pass

    def grab_frame(self) -> QImage | None:
        return None if self._image.isNull() else self._image.copy()
