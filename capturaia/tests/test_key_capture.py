from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from capturaia.ui.key_capture import KeyCaptureButton, qt_key_to_hotkey

K = Qt.Key
M = Qt.KeyboardModifier
NONE = M.NoModifier


@pytest.mark.parametrize(
    ("key", "mods", "expected"),
    [
        (K.Key_F8, NONE, "<f8>"),
        (K.Key_F13, NONE, "<f13>"),
        (K.Key_F24, NONE, "<f24>"),
        (K.Key_G, M.ControlModifier | M.AltModifier, "<ctrl>+<alt>+g"),
        (K.Key_F9, M.ShiftModifier, "<shift>+<f9>"),
        (K.Key_5, NONE, "5"),
        (K.Key_PageDown, NONE, "<page_down>"),
        (K.Key_MediaTogglePlayPause, NONE, "<media_play_pause>"),
        (K.Key_Control, M.ControlModifier, None),  # solo modificador: se espera a la tecla
        (K.Key_Shift, M.ShiftModifier, None),
        (K.Key_unknown, NONE, None),
    ],
)
def test_qt_key_to_hotkey(key: Any, mods: Any, expected: str | None) -> None:
    assert qt_key_to_hotkey(int(key.value), mods) == expected


def _press(widget: Any, key: Any, mods: Any = NONE) -> None:
    widget.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key, mods))


def test_key_capture_button(qtbot: Any) -> None:
    button = KeyCaptureButton("<f8>")
    qtbot.addWidget(button)
    assert button.text() == "F8"
    received: list[str] = []
    button.changed.connect(received.append)

    button.start_capture()
    assert button.capturing
    assert "Pulsa la tecla" in button.text()
    _press(button, K.Key_Control, M.ControlModifier)  # aún no
    assert button.capturing
    _press(button, K.Key_F13, M.ControlModifier)
    assert not button.capturing
    assert button.hotkey == "<ctrl>+<f13>"
    assert button.text() == "Ctrl+F13"
    assert received == ["<ctrl>+<f13>"]

    button.start_capture()
    _press(button, K.Key_Escape)  # cancela sin cambiar
    assert not button.capturing
    assert button.hotkey == "<ctrl>+<f13>"
    assert received == ["<ctrl>+<f13>"]
    assert KeyCaptureButton("").text() == "Sin tecla"
