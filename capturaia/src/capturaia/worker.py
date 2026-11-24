"""Ejecuta las peticiones a Gemini fuera del hilo de la interfaz."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator

from PySide6.QtCore import QObject, QRunnable, Signal

from capturaia.gemini import GeminiError


class AskSignals(QObject):
    chunk = Signal(int, str)  # id, trozo de texto
    finished = Signal(int, str, float)  # id, texto completo, segundos
    failed = Signal(int, str)  # id, mensaje de error


class AskWorker(QRunnable):
    def __init__(self, request_id: int, ask: Callable[[], Iterator[str]]) -> None:
        super().__init__()
        self.request_id = request_id
        self._ask = ask
        self.signals = AskSignals()

    def run(self) -> None:
        started = time.monotonic()
        parts: list[str] = []
        try:
            for piece in self._ask():
                parts.append(piece)
                self.signals.chunk.emit(self.request_id, piece)
        except GeminiError as exc:
            self.signals.failed.emit(self.request_id, str(exc))
            return
        except Exception as exc:  # cualquier fallo debe llegar a la interfaz
            self.signals.failed.emit(self.request_id, f"Error inesperado: {exc!r}")
            return
        text = "".join(parts)
        if not text.strip():
            self.signals.failed.emit(
                self.request_id, "Gemini no devolvió texto (¿respuesta bloqueada o vacía?)."
            )
            return
        self.signals.finished.emit(self.request_id, text, time.monotonic() - started)
