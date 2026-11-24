from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtGui import QImage

from capturaia.capture.image_source import demo_pattern
from capturaia.history import History
from capturaia.imaging import qimage_to_jpeg, thumbnail


def _decode(data: bytes) -> QImage:
    image = QImage()
    assert image.loadFromData(data, "JPG")
    return image


def test_jpeg_keeps_size_when_small_enough(qapp: object) -> None:
    data = qimage_to_jpeg(demo_pattern(1280, 720), quality=80, max_width=1920)
    assert data[:2] == b"\xff\xd8"
    image = _decode(data)
    assert (image.width(), image.height()) == (1280, 720)


def test_jpeg_downscales_and_drops_alpha(qapp: object) -> None:
    source = QImage(3840, 2160, QImage.Format.Format_ARGB32)
    source.fill(0x80FF0000)
    image = _decode(qimage_to_jpeg(source, max_width=1920))
    assert (image.width(), image.height()) == (1920, 1080)


def test_jpeg_rejects_empty_image(qapp: object) -> None:
    with pytest.raises(ValueError, match="vacía"):
        qimage_to_jpeg(QImage())


def test_thumbnail(qapp: object) -> None:
    assert thumbnail(demo_pattern(1920, 1080), 320).width() == 320
    small = demo_pattern(200, 100)
    assert thumbnail(small, 320).width() == 200


def test_history_writes_image_and_note(tmp_path: Path) -> None:
    history = History(tmp_path / "capturas")
    when = datetime(2026, 11, 24, 21, 5, 9)
    first = history.save(
        when=when,
        preset="Analiza",
        prompt="¿Qué ves?",
        jpeg=b"\xff\xd8jpeg",
        answer="Nada.\n",
        model="m",
    )
    second = history.save(when=when, preset="Analiza", prompt="p", jpeg=b"x", answer="a", model="m")
    assert first == tmp_path / "capturas" / "2026-11-24_210509.md"
    assert second == tmp_path / "capturas" / "2026-11-24_210509_2.md"
    assert (tmp_path / "capturas" / "2026-11-24_210509.jpg").read_bytes() == b"\xff\xd8jpeg"
    note = first.read_text(encoding="utf-8")
    assert "# Analiza" in note
    assert "## Pregunta\n\n¿Qué ves?" in note
    assert "## Respuesta\n\nNada.\n" in note
    assert "![captura](2026-11-24_210509.jpg)" in note


def test_history_disabled(tmp_path: Path) -> None:
    history = History(tmp_path / "capturas", enabled=False)
    assert (
        history.save(when=datetime.now(), preset="a", prompt="b", jpeg=b"", answer="c", model="m")
        is None
    )
    assert not (tmp_path / "capturas").exists()
    assert not History(None).enabled
