"""Conversión de frames a JPEG para enviarlos a Gemini."""

from __future__ import annotations

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage


def prepare_image(image: QImage, max_width: int = 0) -> QImage:
    """Reescala (si hace falta) y quita el canal alfa, que JPEG no admite."""
    if max_width and image.width() > max_width:
        image = image.scaledToWidth(max_width, Qt.TransformationMode.SmoothTransformation)
    if image.format() != QImage.Format.Format_RGB888:
        image = image.convertToFormat(QImage.Format.Format_RGB888)
    return image


def qimage_to_jpeg(image: QImage, quality: int = 90, max_width: int = 0) -> bytes:
    if image.isNull():
        msg = "La imagen está vacía."
        raise ValueError(msg)
    image = prepare_image(image, max_width)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "JPG", quality):
        msg = "No se pudo codificar la imagen como JPEG."
        raise RuntimeError(msg)
    return bytes(buffer.data().data())


def thumbnail(image: QImage, width: int) -> QImage:
    if image.isNull() or image.width() <= width:
        return image
    return image.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation)
