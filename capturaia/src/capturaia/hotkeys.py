"""Teclas globales (funcionan aunque la app no tenga el foco) con pynput.

No se usa `pynput.keyboard.GlobalHotKeys` porque compara por carácter y, con Ctrl pulsado,
Windows/X11 entregan caracteres de control ("\\x07" en vez de "g") y la combinación no salta.
Aquí cada tecla se normaliza a un nombre ("ctrl", "f8", "g"...) usando también su código virtual.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from types import ModuleType
from typing import Any

from PySide6.QtCore import QObject, Signal

from capturaia.config import Preset

ACTION_LABELS = {
    "presenter": "«Modo presentación»",
    "scroll": "«Pasar página»",
}
MODIFIERS = frozenset({"ctrl", "alt", "shift", "cmd"})
MODIFIER_ALIASES = {
    "control": "ctrl",
    "ctrl_l": "ctrl",
    "ctrl_r": "ctrl",
    "alt_l": "alt",
    "alt_r": "alt",
    "alt_gr": "alt",
    "shift_l": "shift",
    "shift_r": "shift",
    "win": "cmd",
    "cmd_l": "cmd",
    "cmd_r": "cmd",
}
NAMED_KEYS = frozenset(
    {f"f{n}" for n in range(1, 25)}
    | {
        "space", "enter", "tab", "esc", "backspace", "insert", "delete", "home", "end",
        "page_up", "page_down", "up", "down", "left", "right", "pause", "print_screen",
        "scroll_lock", "num_lock", "caps_lock", "menu", "media_play_pause", "media_next",
        "media_previous", "media_volume_up", "media_volume_down", "media_volume_mute",
    }
)  # fmt: skip


def parse_hotkey(text: str) -> frozenset[str]:
    """'<ctrl>+<alt>+g' -> {'ctrl', 'alt', 'g'}. Lanza ValueError si no es válida."""
    tokens: list[str] = []
    for raw in text.lower().split("+"):
        part = raw.strip()
        if part.startswith("<") and part.endswith(">") and len(part) > 2:
            name = MODIFIER_ALIASES.get(part[1:-1], part[1:-1])
            if name not in MODIFIERS and name not in NAMED_KEYS:
                msg = f"tecla desconocida: {part}"
                raise ValueError(msg)
        elif len(part) == 1 and part.isprintable() and not part.isspace():
            name = part
        else:
            msg = f"no entiendo «{part}»"
            raise ValueError(msg)
        tokens.append(name)
    main_keys = [t for t in tokens if t not in MODIFIERS]
    if len(main_keys) != 1 or len(set(tokens)) != len(tokens):
        msg = "debe haber exactamente una tecla principal (más modificadores opcionales)"
        raise ValueError(msg)
    return frozenset(tokens)


def key_token(key: Any, platform: str = sys.platform) -> str | None:
    """Nombre normalizado de un evento de pynput (Key o KeyCode)."""
    name = getattr(key, "name", None)
    if isinstance(name, str) and name:
        return MODIFIER_ALIASES.get(name, name)
    char = getattr(key, "char", None)
    if isinstance(char, str) and len(char) == 1 and char.isprintable() and not char.isspace():
        return char.lower()
    vk = getattr(key, "vk", None)
    # Windows: VK de dígitos 0x30-0x39 y letras 0x41-0x5A. X11: los keysyms coinciden con
    # ASCII (también minúsculas 0x61-0x7A, que en Windows serían el teclado numérico).
    # En macOS el vk es un código de tecla física sin relación con ASCII: se ignora.
    if isinstance(vk, int) and platform != "darwin" and _is_ascii_key(vk, platform):
        return chr(vk).lower()
    if isinstance(char, str) and len(char) == 1 and 1 <= ord(char) <= 26:
        return chr(ord(char) + 96)  # Ctrl+G llega como "\x07"
    return None


def _is_ascii_key(vk: int, platform: str) -> bool:
    lowercase_ok = platform != "win32" and 0x61 <= vk <= 0x7A
    return 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A or lowercase_ok


class HotkeyMatcher:
    """Lleva la cuenta de las teclas pulsadas y dice qué combinación se acaba de completar."""

    def __init__(self, combos: dict[frozenset[str], int]) -> None:
        self._combos = combos
        self._pressed: set[str] = set()
        self._latched: set[frozenset[str]] = set()  # evita repetir mientras se mantiene pulsada

    def press(self, token: str | None) -> int | None:
        if token is None:
            return None
        self._pressed.add(token)
        if token in MODIFIERS:
            return None
        # Solo cuentan los modificadores pulsados + la tecla recién pulsada; así una tecla
        # normal "atascada" (p. ej. por perder un evento de soltar) no bloquea las combinaciones.
        current = frozenset({t for t in self._pressed if t in MODIFIERS} | {token})
        if current in self._latched:
            return None
        index = self._combos.get(current)
        if index is not None:
            self._latched.add(current)
        return index

    def release(self, token: str | None) -> None:
        if token is None:
            return
        self._pressed.discard(token)
        self._latched = {combo for combo in self._latched if token not in combo}


class HotkeyBridge(QObject):
    """Escucha las teclas globales y avisa en el hilo de Qt.

    - `triggered(indice_preset)` para las preguntas prefijadas.
    - `action(nombre)` para el resto de acciones (p. ej. "presenter", "scroll").
    """

    triggered = Signal(int)
    action = Signal(str)

    def __init__(
        self,
        presets: Sequence[Preset],
        parent: QObject | None = None,
        *,
        actions: Mapping[str, str] | None = None,
        keyboard_module: ModuleType | Any = None,
    ) -> None:
        super().__init__(parent)
        self._presets = list(presets)
        self._actions = dict(actions or {})
        self._keyboard = keyboard_module
        self._listener: Any = None
        self._matcher: HotkeyMatcher | None = None
        self._targets: list[int | str] = []  # índice de preset o nombre de acción
        self.active: dict[str, int | str] = {}

    def start(self) -> list[str]:
        """Arranca la escucha y devuelve avisos para el usuario (vacío si todo va bien)."""
        keyboard = self._keyboard
        if keyboard is None:
            try:
                from pynput import keyboard  # noqa: PLC0415
            except Exception as exc:  # p. ej. Linux sin servidor gráfico
                return [f"Teclas globales no disponibles ({exc}). Usa el botón «Preguntar»."]

        entries: list[tuple[str, str, int | str]] = [
            (preset.hotkey, f"«{preset.name}»", index) for index, preset in enumerate(self._presets)
        ]
        entries += [
            (hotkey, ACTION_LABELS.get(name, name), name) for name, hotkey in self._actions.items()
        ]

        warnings: list[str] = []
        combos: dict[frozenset[str], int] = {}
        labels: dict[frozenset[str], str] = {}
        for hotkey, label, target in entries:
            if not hotkey:
                continue
            try:
                combo = parse_hotkey(hotkey)
            except ValueError as exc:
                warnings.append(f"Tecla no válida en {label} ({hotkey}): {exc}")
                continue
            if combo in combos:
                warnings.append(
                    f"La tecla {hotkey} ya la usa {labels[combo]}; ignorada en {label}."
                )
                continue
            combos[combo] = len(self._targets)
            labels[combo] = label
            self._targets.append(target)
            self.active[hotkey] = target

        if combos:
            self._matcher = HotkeyMatcher(combos)
            self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
            self._listener.daemon = True
            self._listener.start()
        return warnings

    # Estos dos se llaman desde el hilo de pynput; emitir la señal es seguro entre hilos
    # (Qt la encola y la entrega en el hilo de la interfaz).
    def _on_press(self, key: Any) -> None:
        if self._matcher is None:
            return
        found = self._matcher.press(key_token(key))
        if found is None:
            return
        target = self._targets[found]
        if isinstance(target, str):
            self.action.emit(target)
        else:
            self.triggered.emit(target)

    def _on_release(self, key: Any) -> None:
        if self._matcher is not None:
            self._matcher.release(key_token(key))

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None


def pretty_hotkey(hotkey: str) -> str:
    """'<ctrl>+<alt>+g' -> 'Ctrl+Alt+G'."""
    if not hotkey:
        return ""
    pieces = []
    for raw in hotkey.split("+"):
        key = raw.strip().strip("<>")
        is_fkey = key[:1] == "f" and key[1:].isdigit()
        pieces.append(key.upper() if is_fkey or len(key) == 1 else key.capitalize())
    return "+".join(pieces)
