"""Interfaz común de las fuentes de vídeo."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

from PySide6.QtCore import QObject, QSize, Signal
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

    def frame_size(self) -> QSize | None:
        """Tamaño de la imagen que llega (para repartir la pantalla), o None si no se sabe."""
        return None

    def measured_fps(self) -> float | None:
        """Frames por segundo que llegan de verdad (diagnóstico), o None si no aplica."""
        return None


class FpsMeter:
    """Cuenta frames y da la media de los últimos segundos."""

    def __init__(self, window_s: float = 2.0, clock: Callable[[], float] = time.monotonic) -> None:
        self._window = window_s
        self._clock = clock
        self._stamps: deque[float] = deque()

    def tick(self) -> None:
        now = self._clock()
        self._stamps.append(now)
        while self._stamps and now - self._stamps[0] > self._window:
            self._stamps.popleft()

    def fps(self) -> float:
        now = self._clock()
        while self._stamps and now - self._stamps[0] > self._window:
            self._stamps.popleft()
        if len(self._stamps) < 2:
            return 0.0
        span = self._stamps[-1] - self._stamps[0]
        return (len(self._stamps) - 1) / span if span > 0 else 0.0


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
