"""Fuentes de vídeo intercambiables."""

from __future__ import annotations

from capturaia.capture.base import FrameSource
from capturaia.config import CaptureConfig


def list_devices(config: CaptureConfig) -> list[str]:
    if config.backend == "qt":
        from capturaia.capture.qt_source import list_devices as qt_devices  # noqa: PLC0415

        return qt_devices()
    if config.backend == "opencv":
        from capturaia.capture.opencv_source import list_devices as cv_devices  # noqa: PLC0415

        return cv_devices()
    return []


def create_source(config: CaptureConfig, device: str | None = None) -> FrameSource:
    device = config.device if device is None else device
    if config.backend == "qt":
        from capturaia.capture.qt_source import QtCameraSource  # noqa: PLC0415

        return QtCameraSource(device, config.width, config.height, config.fps)
    if config.backend == "opencv":
        from capturaia.capture.opencv_source import OpenCvSource  # noqa: PLC0415

        return OpenCvSource(device, config.width, config.height, config.fps, config.fourcc)
    from capturaia.capture.image_source import ImageFileSource  # noqa: PLC0415

    return ImageFileSource(config.image_path)


__all__ = ["FrameSource", "create_source", "list_devices"]
