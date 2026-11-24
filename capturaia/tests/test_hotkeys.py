from __future__ import annotations

import builtins
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from capturaia.config import Preset
from capturaia.hotkeys import HotkeyBridge, HotkeyMatcher, key_token, parse_hotkey, pretty_hotkey


def named(name: str) -> Any:
    """Imita pynput.keyboard.Key (tiene .name)."""
    return SimpleNamespace(name=name)


def code(char: str | None = None, vk: int | None = None) -> Any:
    """Imita pynput.keyboard.KeyCode (tiene .char y .vk)."""
    return SimpleNamespace(char=char, vk=vk)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("<f8>", {"f8"}),
        ("<CTRL>+<Alt>+G", {"ctrl", "alt", "g"}),
        ("<ctrl_l>+<shift>+<f13>", {"ctrl", "shift", "f13"}),
        ("<win>+1", {"cmd", "1"}),
        ("<media_play_pause>", {"media_play_pause"}),
    ],
)
def test_parse_hotkey(text: str, expected: set[str]) -> None:
    assert parse_hotkey(text) == frozenset(expected)


@pytest.mark.parametrize(
    "text", ["", "<ctrl>", "<ctrl>+<alt>", "g+h", "<f99>", "<nope>", "<ctrl>+gg", "<f8>+<f8>"]
)
def test_parse_hotkey_invalid(text: str) -> None:
    with pytest.raises(ValueError, match=r"."):
        parse_hotkey(text)


@pytest.mark.parametrize(
    ("key", "platform", "token"),
    [
        (named("ctrl_l"), "win32", "ctrl"),
        (named("alt_gr"), "win32", "alt"),
        (named("f8"), "win32", "f8"),
        (code("G", 0x47), "win32", "g"),
        (code("\x07", 0x47), "win32", "g"),  # Ctrl+G en Windows
        (code(None, 0x47), "win32", "g"),
        (code(None, 0x61), "win32", None),  # VK_NUMPAD1, no es una "a"
        (code(None, 0x61), "linux", "a"),  # keysym de "a" en X11
        (code("\x07", None), "linux", "g"),
        (code("ñ", None), "win32", "ñ"),
        (code(None, 0x00), "darwin", None),
        (code(None, None), "win32", None),
    ],
)
def test_key_token(key: Any, platform: str, token: str | None) -> None:
    assert key_token(key, platform) == token


def test_matcher_combos_and_autorepeat() -> None:
    matcher = HotkeyMatcher(
        {frozenset({"f8"}): 0, frozenset({"ctrl", "alt", "g"}): 1, frozenset({"shift", "f9"}): 2}
    )
    # F8 mantenido (autorepetición) solo dispara una vez hasta que se suelta.
    assert matcher.press("f8") == 0
    assert matcher.press("f8") is None
    matcher.release("f8")
    assert matcher.press("f8") == 0
    matcher.release("f8")

    assert matcher.press("ctrl") is None
    assert matcher.press("alt") is None
    assert matcher.press("g") == 1
    matcher.release("g")
    assert matcher.press("g") == 1  # se puede repetir sin soltar los modificadores
    for key in ("g", "alt", "ctrl"):
        matcher.release(key)

    assert matcher.press("g") is None  # sin modificadores no es la combinación
    assert matcher.press("f9") is None
    matcher.release("f9")
    matcher.press("shift")
    assert matcher.press("f9") == 2  # la "g" atascada no molesta
    assert matcher.press(None) is None
    matcher.release(None)


def test_matcher_extra_modifier_does_not_match() -> None:
    matcher = HotkeyMatcher({frozenset({"f8"}): 0})
    matcher.press("ctrl")
    assert matcher.press("f8") is None


class FakeListener:
    instances: ClassVar[list[FakeListener]] = []

    def __init__(self, on_press: Any, on_release: Any) -> None:
        self.on_press = on_press
        self.on_release = on_release
        self.started = self.stopped = False
        FakeListener.instances.append(self)

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


FAKE_KEYBOARD = SimpleNamespace(Listener=FakeListener)


def test_hotkey_bridge(qapp: object) -> None:
    presets = [
        Preset("A", "pa", "<f8>"),
        Preset("B", "pb", ""),
        Preset("C", "pc", "<F8>"),
        Preset("D", "pd", "<ctrl>+<nope>"),
        Preset("E", "pe", "<ctrl>+<alt>+g"),
    ]
    bridge = HotkeyBridge(presets, keyboard_module=FAKE_KEYBOARD)
    fired: list[int] = []
    bridge.triggered.connect(fired.append)
    warnings = bridge.start()
    assert len(warnings) == 2
    assert "ya la usa «A»" in warnings[0]
    assert "no válida" in warnings[1]
    assert bridge.active == {"<f8>": 0, "<ctrl>+<alt>+g": 4}

    listener = FakeListener.instances[-1]
    assert listener.started
    listener.on_press(named("ctrl_r"))
    listener.on_press(named("alt_l"))
    listener.on_press(code("\x07", 0x47))
    for key in (code("\x07", 0x47), named("alt_l"), named("ctrl_r")):
        listener.on_release(key)
    listener.on_press(named("f8"))
    assert fired == [4, 0]
    bridge.stop()
    assert listener.stopped


def test_hotkey_bridge_without_hotkeys_does_not_listen(qapp: object) -> None:
    before = len(FakeListener.instances)
    bridge = HotkeyBridge([Preset("A", "p", "")], keyboard_module=FAKE_KEYBOARD)
    assert bridge.start() == []
    assert len(FakeListener.instances) == before
    bridge.stop()


def test_hotkey_bridge_without_backend(qapp: object, monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def failing_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "pynput":
            raise ImportError("sin servidor gráfico")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", failing_import)
    bridge = HotkeyBridge([Preset("A", "p", "<f8>")])
    warnings = bridge.start()
    assert "no disponibles" in warnings[0]
    assert bridge.active == {}


@pytest.mark.parametrize(
    ("raw", "pretty"),
    [("<f8>", "F8"), ("<ctrl>+<alt>+g", "Ctrl+Alt+G"), ("<shift>+<f13>", "Shift+F13"), ("", "")],
)
def test_pretty_hotkey(raw: str, pretty: str) -> None:
    assert pretty_hotkey(raw) == pretty


def test_hotkey_bridge_actions(qapp: object) -> None:
    bridge = HotkeyBridge(
        [Preset("A", "pa", "<f8>"), Preset("B", "pb", "<f10>")],
        actions={"presenter": "<f12>", "scroll": "<f10>", "otra": "<f99>"},
        keyboard_module=FAKE_KEYBOARD,
    )
    presets: list[int] = []
    actions: list[str] = []
    bridge.triggered.connect(presets.append)
    bridge.action.connect(actions.append)
    warnings = bridge.start()
    assert len(warnings) == 2
    assert "ya la usa «B»" in warnings[0]
    assert "«Pasar página»" in warnings[0]
    assert "no válida en otra" in warnings[1]
    assert bridge.active == {"<f8>": 0, "<f10>": 1, "<f12>": "presenter"}

    listener = FakeListener.instances[-1]
    for name in ("f12", "f8", "f10"):
        listener.on_press(named(name))
        listener.on_release(named(name))
    assert actions == ["presenter"]
    assert presets == [0, 1]
    bridge.stop()
