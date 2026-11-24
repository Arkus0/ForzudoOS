"""Fuente alternativa con OpenCV (DirectShow en Windows).

Úsala si la capturadora no funciona bien con el backend "qt". Necesita el extra opencv:
`uv sync --extra opencv`.
"""

from __future__ import annotations

import sys
import threading
from typing import Any

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from capturaia.capture.base import FpsMeter, FrameSource

MAX_INDEX = 6


def list_devices() -> list[str]:
    """OpenCV no da nombres; se ofrecen índices (0 suele ser la primera cámara/capturadora)."""
    return [str(i) for i in range(MAX_INDEX)]


def bgr_to_qimage(frame: Any) -> QImage:
    height, width = frame.shape[:2]
    image = QImage(frame.data, width, height, frame.strides[0], QImage.Format.Format_BGR888)
    return image.copy()  # se desliga del buffer de numpy


class OpenCvSource(FrameSource):
    def __init__(self, device: str, width: int, height: int, fps: int, fourcc: str = "") -> None:
        super().__init__()
        self._index = int(device) if device.strip().isdigit() else 0
        self._size = (width, height, fps)
        self._fourcc = fourcc
        self._label = QLabel("Abriendo capturadora…")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setMinimumSize(160, 90)
        self._label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self._label.setStyleSheet("background: black; color: #aaa;")
        self._lock = threading.Lock()
        self._frame: Any = None
        self._running = threading.Event()
        self._fps = FpsMeter()
        self._thread: threading.Thread | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(33)  # vista previa a ~30 fps, suficiente y barata
        self._timer.timeout.connect(self._refresh_preview)

    def preview_widget(self) -> QWidget:
        return self._label

    def start(self) -> None:
        try:
            import cv2  # noqa: PLC0415
        except ImportError:
            self.error.emit("Falta OpenCV. Instálalo con: uv sync --extra opencv")
            return
        api = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        capture = cv2.VideoCapture(self._index, api)
        if not capture.isOpened():
            self.error.emit(f"OpenCV no pudo abrir el dispositivo {self._index}.")
            return
        width, height, fps = self._size
        if self._fourcc:
            capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self._fourcc))
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        capture.set(cv2.CAP_PROP_FPS, fps)
        real = (
            int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            capture.get(cv2.CAP_PROP_FPS),
        )
        self._running.set()
        self._thread = threading.Thread(target=self._read_loop, args=(capture,), daemon=True)
        self._thread.start()
        self._timer.start()
        self.status.emit(
            f"OpenCV dispositivo {self._index} · {real[0]}x{real[1]} @ {real[2]:.0f} fps"
        )

    def _read_loop(self, capture: Any) -> None:
        failures = 0
        while self._running.is_set():
            ok, frame = capture.read()
            if not ok:
                failures += 1
                if failures > 100:
                    break
                continue
            failures = 0
            with self._lock:
                self._frame = frame
                self._fps.tick()
        capture.release()

    def _latest(self) -> Any:
        with self._lock:
            return self._frame

    def _refresh_preview(self) -> None:
        frame = self._latest()
        if frame is None:
            return
        import cv2  # noqa: PLC0415

        target = self._label.size()
        h, w = frame.shape[:2]
        scale = min(target.width() / w, target.height() / h)
        if scale <= 0:
            return
        small = cv2.resize(frame, (max(1, int(w * scale)), max(1, int(h * scale))))
        self._label.setPixmap(QPixmap.fromImage(bgr_to_qimage(small)))

    def stop(self) -> None:
        self._timer.stop()
        self._running.clear()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def grab_frame(self) -> QImage | None:
        frame = self._latest()
        return None if frame is None else bgr_to_qimage(frame)

    def frame_size(self) -> QSize | None:
        frame = self._latest()
        return None if frame is None else QSize(frame.shape[1], frame.shape[0])

    def measured_fps(self) -> float | None:
        if self._thread is None:
            return None
        with self._lock:
            return self._fps.fps()
