"""Interfaz común de las fuentes de vídeo."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget


class FrameSource(QObject):
    """Una fuente de vídeo con vista previa y captura del frame actual."""

    status = Signal(str)  # mensajes informativos (p. ej. "1920x1080 @ 60 fps")
    error = Signal(str)  # errores para mostrar al usuario

    def preview_widget(self) -> QWidget:
        raise NotImplementedError

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def grab_frame(self) -> QImage | None:
        """Copia del último frame recibido, o None si todavía no hay imagen."""
        raise NotImplementedError


def match_device(names: list[str], wanted: str) -> int | None:
    """Índice del primer dispositivo cuyo nombre contiene `wanted` (sin distinguir mayúsculas)."""
    wanted = wanted.strip().lower()
    if not wanted:
        return 0 if names else None
    for index, name in enumerate(names):
        if name.lower() == wanted:
            return index
    for index, name in enumerate(names):
        if wanted in name.lower():
            return index
    return None
