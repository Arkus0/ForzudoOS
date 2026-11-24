"""Fuente principal: Qt Multimedia (la capturadora se ve como una cámara)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QCameraPermission, QCoreApplication, QSize, Qt
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import (
    QCamera,
    QCameraDevice,
    QCameraFormat,
    QMediaCaptureSession,
    QMediaDevices,
    QVideoFrameFormat,
)
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QWidget

from capturaia.capture.base import FpsMeter, FrameSource, match_device

PERMISSION_HELP = (
    "Windows ha bloqueado el acceso a la cámara/capturadora. Actívalo en Configuración > "
    "Privacidad y seguridad > Cámara > «Permitir que las aplicaciones de escritorio accedan "
    "a la cámara»."
)


def list_devices() -> list[str]:
    return [device.description() for device in QMediaDevices.videoInputs()]


def choose_format(formats: Sequence[Any], width: int, height: int, fps: int) -> Any | None:
    """Elige el formato más parecido al pedido.

    Prioridad: resolución exacta, después la más cercana; alcanzar los fps pedidos sin pasarse
    de más; preferir formatos sin comprimir (YUY2/NV12) frente a MJPEG, que pierde calidad.
    """

    def score(fmt: Any) -> tuple[bool, int, float, bool, float]:
        res = fmt.resolution()
        exact = res.width() == width and res.height() == height
        area_gap = abs(res.width() * res.height() - width * height)
        rate = float(fmt.maxFrameRate())
        uncompressed = fmt.pixelFormat() != QVideoFrameFormat.PixelFormat.Format_Jpeg
        return (exact, -area_gap, min(rate, float(fps)), uncompressed, -rate)

    return max(formats, key=score, default=None)


def describe_format(fmt: QCameraFormat) -> str:
    res = fmt.resolution()
    pixel = fmt.pixelFormat().name.removeprefix("Format_")
    return f"{res.width()}x{res.height()} @ {fmt.maxFrameRate():.0f} fps ({pixel})"


class QtCameraSource(FrameSource):
    def __init__(self, device: str, width: int, height: int, fps: int) -> None:
        super().__init__()
        self._wanted_device = device
        self._size = (width, height, fps)
        self._widget = QVideoWidget()
        self._widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self._session = QMediaCaptureSession()
        self._session.setVideoOutput(self._widget)
        self._camera: QCamera | None = None
        self._fps = FpsMeter()
        self._widget.videoSink().videoFrameChanged.connect(self._on_frame)

    def preview_widget(self) -> QWidget:
        return self._widget

    def start(self) -> None:
        app = QCoreApplication.instance()
        permission = QCameraPermission()
        status = app.checkPermission(permission) if app else Qt.PermissionStatus.Granted
        if status == Qt.PermissionStatus.Undetermined and app is not None:
            try:
                app.requestPermission(permission, self, self._after_permission)
            except TypeError:
                self._open_camera()
            return
        if status == Qt.PermissionStatus.Denied:
            self.error.emit(PERMISSION_HELP)
            return
        self._open_camera()

    def _after_permission(self, permission: Any) -> None:
        app = QCoreApplication.instance()
        if app and app.checkPermission(permission) == Qt.PermissionStatus.Granted:
            self._open_camera()
        else:
            self.error.emit(PERMISSION_HELP)

    def _open_camera(self) -> None:
        devices: list[QCameraDevice] = list(QMediaDevices.videoInputs())
        names = [d.description() for d in devices]
        index = match_device(names, self._wanted_device)
        if index is None:
            if names:
                available = ", ".join(f"«{n}»" for n in names)
                self.error.emit(f"No encuentro «{self._wanted_device}». Disponibles: {available}")
            else:
                self.error.emit("No hay ninguna capturadora ni cámara conectada.")
            return
        device = devices[index]
        camera = QCamera(device)
        fmt = choose_format(device.videoFormats(), *self._size)
        if fmt is not None:
            camera.setCameraFormat(fmt)
        camera.errorOccurred.connect(self._on_camera_error)
        self._session.setCamera(camera)
        self._camera = camera
        camera.start()
        detail = f" · {describe_format(fmt)}" if fmt is not None else ""
        self.status.emit(f"{device.description()}{detail}")

    def _on_camera_error(self, _error: QCamera.Error, message: str) -> None:
        self.error.emit(f"Error de la capturadora: {message}")

    def stop(self) -> None:
        if self._camera is not None:
            self._camera.stop()
            self._session.setCamera(None)
            self._camera.deleteLater()
            self._camera = None

    def _on_frame(self, _frame: object) -> None:
        self._fps.tick()

    def measured_fps(self) -> float | None:
        return self._fps.fps() if self._camera is not None else None

    def frame_size(self) -> QSize | None:
        size = self._widget.videoSink().videoSize()
        return size if size.isValid() and not size.isEmpty() else None

    def grab_frame(self) -> QImage | None:
        frame = self._widget.videoSink().videoFrame()
        if not frame.isValid():
            return None
        image = frame.toImage()
        return None if image.isNull() else image
