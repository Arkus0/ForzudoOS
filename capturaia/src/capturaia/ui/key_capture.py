"""Botón para asignar una tecla pulsándola (sirve también para los botones de un mando)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFocusEvent, QKeyEvent
from PySide6.QtWidgets import QPushButton, QWidget

from capturaia.hotkeys import parse_hotkey, pretty_hotkey

K = Qt.Key


def _v(key: K) -> int:
    return int(key.value)


_NAMED = {
    _v(K.Key_Space): "space",
    _v(K.Key_Return): "enter",
    _v(K.Key_Enter): "enter",
    _v(K.Key_Tab): "tab",
    _v(K.Key_Backspace): "backspace",
    _v(K.Key_Insert): "insert",
    _v(K.Key_Delete): "delete",
    _v(K.Key_Home): "home",
    _v(K.Key_End): "end",
    _v(K.Key_PageUp): "page_up",
    _v(K.Key_PageDown): "page_down",
    _v(K.Key_Up): "up",
    _v(K.Key_Down): "down",
    _v(K.Key_Left): "left",
    _v(K.Key_Right): "right",
    _v(K.Key_Pause): "pause",
    _v(K.Key_Print): "print_screen",
    _v(K.Key_ScrollLock): "scroll_lock",
    _v(K.Key_NumLock): "num_lock",
    _v(K.Key_CapsLock): "caps_lock",
    _v(K.Key_Menu): "menu",
    _v(K.Key_MediaTogglePlayPause): "media_play_pause",
    _v(K.Key_MediaPlay): "media_play_pause",
    _v(K.Key_MediaNext): "media_next",
    _v(K.Key_MediaPrevious): "media_previous",
    _v(K.Key_VolumeUp): "media_volume_up",
    _v(K.Key_VolumeDown): "media_volume_down",
    _v(K.Key_VolumeMute): "media_volume_mute",
}
_MODIFIER_KEYS = {
    _v(K.Key_Control),
    _v(K.Key_Shift),
    _v(K.Key_Alt),
    _v(K.Key_AltGr),
    _v(K.Key_Meta),
    _v(K.Key_unknown),
}
_MODIFIERS = (
    (Qt.KeyboardModifier.ControlModifier, "<ctrl>"),
    (Qt.KeyboardModifier.AltModifier, "<alt>"),
    (Qt.KeyboardModifier.ShiftModifier, "<shift>"),
    (Qt.KeyboardModifier.MetaModifier, "<cmd>"),
)


def qt_key_to_hotkey(key: int, modifiers: Qt.KeyboardModifier) -> str | None:
    """Tecla de Qt -> formato de CapturaIA ("<f8>", "<ctrl>+<alt>+g"). None si no vale sola."""
    if key in _MODIFIER_KEYS:
        return None
    if _v(K.Key_F1) <= key <= _v(K.Key_F24):
        main = f"<f{key - _v(K.Key_F1) + 1}>"
    elif key in _NAMED:
        main = f"<{_NAMED[key]}>"
    elif 0x20 < key < 0x7F:
        main = chr(key).lower()
    else:
        return None
    mods = [name for flag, name in _MODIFIERS if modifiers & flag]
    hotkey = "+".join([*mods, main])
    try:
        parse_hotkey(hotkey)
    except ValueError:
        return None
    return hotkey


class KeyCaptureButton(QPushButton):
    """Muestra la tecla asignada; al pulsarlo, la siguiente tecla (o botón del mando) la cambia."""

    changed = Signal(str)
    capturing_changed = Signal(bool)

    def __init__(self, hotkey: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._hotkey = hotkey
        self.capturing = False
        self.setMinimumWidth(130)
        self.setToolTip("Pulsa aquí y después la tecla o el botón del mando que quieras usar")
        self.clicked.connect(self.start_capture)
        self._refresh()

    @property
    def hotkey(self) -> str:
        return self._hotkey

    def set_hotkey(self, hotkey: str) -> None:
        self._hotkey = hotkey
        self._refresh()

    def _refresh(self) -> None:
        if self.capturing:
            self.setText("Pulsa la tecla… (Esc cancela)")
        else:
            self.setText(pretty_hotkey(self._hotkey) or "Sin tecla")

    def start_capture(self) -> None:
        self.capturing = True
        self._refresh()
        self.setFocus()
        self.grabKeyboard()
        self.capturing_changed.emit(True)

    def _stop_capture(self) -> None:
        if self.capturing:
            self.capturing = False
            self.releaseKeyboard()
            self._refresh()
            self.capturing_changed.emit(False)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not self.capturing:
            super().keyPressEvent(event)
            return
        if event.key() == _v(K.Key_Escape):
            self._stop_capture()
            return
        hotkey = qt_key_to_hotkey(event.key(), event.modifiers())
        if hotkey is None:
            return  # solo un modificador: se espera a la tecla principal
        self._hotkey = hotkey
        self._stop_capture()
        self.changed.emit(hotkey)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        self._stop_capture()
        super().focusOutEvent(event)
