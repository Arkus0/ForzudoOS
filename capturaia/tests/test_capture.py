from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PySide6.QtMultimedia import QVideoFrameFormat

from capturaia.capture import create_source, list_devices
from capturaia.capture.base import match_device
from capturaia.capture.image_source import ImageFileSource, demo_pattern
from capturaia.capture.qt_source import QtCameraSource, choose_format
from capturaia.config import AppConfig

JPEG = QVideoFrameFormat.PixelFormat.Format_Jpeg
NV12 = QVideoFrameFormat.PixelFormat.Format_NV12


def _fmt(w: int, h: int, fps: float, pixel: Any = NV12) -> Any:
    return SimpleNamespace(
        resolution=lambda: SimpleNamespace(width=lambda: w, height=lambda: h),
        maxFrameRate=lambda: fps,
        pixelFormat=lambda: pixel,
        label=f"{w}x{h}@{fps}/{pixel.name}",
    )


def test_match_device() -> None:
    names = ["Integrated Webcam", "Game Capture HD60 S+", "OBS Virtual Camera"]
    assert match_device(names, "") == 0
    assert match_device(names, "hd60") == 1
    assert match_device(names, "obs virtual camera") == 2
    assert match_device(names, "elgato 4k") is None
    assert match_device([], "") is None


@pytest.mark.parametrize(
    ("formats", "expected"),
    [
        # Prefiere la resolución exacta aunque otra tenga más fps.
        ([_fmt(1280, 720, 60), _fmt(1920, 1080, 30)], "1920x1080@30/Format_NV12"),
        # A igual resolución, la que alcanza los fps pedidos.
        ([_fmt(1920, 1080, 30), _fmt(1920, 1080, 60)], "1920x1080@60/Format_NV12"),
        # A igualdad, sin comprimir antes que MJPEG.
        ([_fmt(1920, 1080, 60, JPEG), _fmt(1920, 1080, 60)], "1920x1080@60/Format_NV12"),
        # Sin la exacta, la más cercana.
        ([_fmt(640, 480, 60), _fmt(2560, 1440, 60)], "2560x1440@60/Format_NV12"),
        # No premia pasarse de fps: a 120 y 60 pedidos 60, gana 60.
        ([_fmt(1920, 1080, 120), _fmt(1920, 1080, 60)], "1920x1080@60/Format_NV12"),
    ],
)
def test_choose_format(formats: list[Any], expected: str) -> None:
    assert choose_format(formats, 1920, 1080, 60).label == expected


def test_choose_format_empty() -> None:
    assert choose_format([], 1920, 1080, 60) is None


def test_image_source_demo(qapp: object, qtbot: Any) -> None:
    source = ImageFileSource("")
    statuses: list[str] = []
    source.status.connect(statuses.append)
    qtbot.addWidget(source.preview_widget())
    source.start()
    frame = source.grab_frame()
    assert frame is not None
    assert (frame.width(), frame.height()) == (1920, 1080)
    assert "imagen de prueba" in statuses[0]


def test_image_source_file_and_bad_path(qapp: object, qtbot: Any, tmp_path: Path) -> None:
    path = tmp_path / "frame.png"
    demo_pattern(640, 360).save(str(path))
    source = ImageFileSource(str(path))
    qtbot.addWidget(source.preview_widget())
    assert source.grab_frame().width() == 640

    bad = ImageFileSource(str(tmp_path / "no-existe.png"))
    errors: list[str] = []
    bad.error.connect(errors.append)
    qtbot.addWidget(bad.preview_widget())
    assert errors
    assert bad.grab_frame() is not None  # cae en la imagen de prueba


def test_create_source_by_backend(qapp: object, qtbot: Any, config: AppConfig) -> None:
    assert isinstance(create_source(config.capture), ImageFileSource)
    assert list_devices(config.capture) == []
    qt_capture = replace(config.capture, backend="qt")
    source = create_source(qt_capture, "lo que sea")
    qtbot.addWidget(source.preview_widget())
    assert isinstance(source, QtCameraSource)
    assert source.grab_frame() is None  # sin cámara no hay frames


def test_qt_source_without_devices_reports_error(qapp: object, qtbot: Any) -> None:
    source = QtCameraSource("", 1920, 1080, 60)
    qtbot.addWidget(source.preview_widget())
    errors: list[str] = []
    source.error.connect(errors.append)
    source.start()
    assert errors
    assert "No hay ninguna" in errors[0]
