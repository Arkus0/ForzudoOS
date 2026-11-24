from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest
from PySide6.QtCore import QSettings, Qt, QThreadPool
from PySide6.QtWidgets import QMessageBox

from capturaia import app as app_module
from capturaia.app import CapturaApp
from capturaia.config import AppConfig, GeminiConfig, Preset, load_config
from capturaia.gemini import GeminiError
from capturaia.history import History
from capturaia.phone import PhoneServer, PhoneState
from capturaia.ui.setup_window import AUTO_START_S, SetupWindow


class FakeAsker:
    fail_check: ClassVar[str] = ""

    def __init__(self, gemini: GeminiConfig) -> None:
        self.model = gemini.model
        self.key = gemini.api_key

    def check(self) -> str:
        if FakeAsker.fail_check:
            raise GeminiError(FakeAsker.fail_check)
        return "Gemini Flash"

    def list_models(self) -> list[str]:
        return ["gemini-3.8-flash", "gemini-9-pro"]

    def ask_stream(self, jpeg: bytes, prompt: str) -> Iterator[str]:
        yield "- **Uno**\n"
        yield "- Dos"


@pytest.fixture(autouse=True)
def _reset_fake() -> None:
    FakeAsker.fail_check = ""


@pytest.fixture
def setup_cfg(config: AppConfig) -> AppConfig:
    return replace(config, gemini=replace(config.gemini, api_key="AIza-prueba"))


@pytest.fixture
def make_setup(qtbot: Any, setup_cfg: AppConfig) -> Any:
    windows: list[SetupWindow] = []

    def make(cfg: AppConfig | None = None, **kwargs: Any) -> SetupWindow:
        kwargs.setdefault("asker_factory", FakeAsker)
        kwargs.setdefault("thread_pool", QThreadPool())
        window = SetupWindow(cfg or setup_cfg, **kwargs)
        window._refresh_timer.stop()  # los tests avanzan el reloj a mano con _tick()
        qtbot.addWidget(window)
        windows.append(window)
        return window

    yield make
    for window in windows:
        window._pool.waitForDone(5000)


def _phone() -> tuple[PhoneServer, PhoneState]:
    state = PhoneState()
    return PhoneServer(state, "tok", 0, 40), state


def _all_green(window: SetupWindow, state: PhoneState, qtbot: Any) -> None:
    qtbot.waitUntil(lambda: window.check_state("Gemini") is True, timeout=5000)
    window.set_hotkeys_status(True, "activas")
    state.snapshot(None, awake=True)  # el móvil está leyendo con la pantalla fija
    window._tick()


def test_fields_start_from_config(make_setup: Any, setup_cfg: AppConfig) -> None:
    window = make_setup()
    assert window.api_key.text() == "AIza-prueba"
    assert window.model.currentText() == setup_cfg.gemini.model
    assert [r.preset() for r in window.rows] == list(setup_cfg.presets)
    assert window.scroll_key.hotkey == "<f10>"


def test_save_and_start_writes_config(make_setup: Any, setup_cfg: AppConfig) -> None:
    window = make_setup(auto_start=False)
    started: list[AppConfig] = []
    window.start_requested.connect(started.append)
    window.api_key.setText("AIza-nueva")
    window.model.setCurrentText("gemini-3.5-flash-lite")
    window._remove_row(window.rows[2])
    row = window._add_row(Preset(name="", prompt="", hotkey=""))
    row.name.setText("Resumen")
    row.prompt.setPlainText("Resume en una frase.")
    row.key.set_hotkey("<ctrl>+<f13>")

    cfg = window.save_and_start(confirm=False)
    assert cfg is not None
    assert started == [cfg]
    saved = load_config(setup_cfg.path)
    assert saved.gemini.api_key == "AIza-nueva"
    assert saved.gemini.model == "gemini-3.5-flash-lite"
    assert [p.name for p in saved.presets] == ["Explícame esto", "Pon un ejemplo", "Resumen"]
    assert saved.presets[2].hotkey == "<ctrl>+<f13>"


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        (lambda w: w.rows[1].key.set_hotkey("<f8>"), "ya la usa «Explícame esto»"),
        (lambda w: w.scroll_key.set_hotkey("<f9>"), "ya la usa «Pon un ejemplo»"),
        (lambda w: w.rows[0].prompt.setPlainText("  "), "necesita nombre y texto"),
        (lambda w: [w._remove_row(r) for r in list(w.rows)], "al menos una pregunta"),
        (lambda w: w.model.setCurrentText(""), "modelo"),
    ],
)
def test_invalid_setups_are_not_saved(
    make_setup: Any, monkeypatch: pytest.MonkeyPatch, change: Any, fragment: str
) -> None:
    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _p, _t, text: warnings.append(text))
    window = make_setup(auto_start=False)
    started: list[Any] = []
    window.start_requested.connect(started.append)
    change(window)
    assert window.save_and_start(confirm=False) is None
    assert started == []
    assert fragment in warnings[0]


def test_checks_go_green_and_start_by_themselves(make_setup: Any, qtbot: Any) -> None:
    phone, state = _phone()
    window = make_setup(phone=phone)
    window.set_usb("adb.exe", "http://localhost:8765")
    window.set_usb_status("Móvil conectado sin cable: abre http://localhost:8765/…", True)
    started: list[AppConfig] = []
    window.start_requested.connect(started.append)

    window._tick()
    assert window.check_state("Móvil") is False  # el móvil aún no ha abierto la página
    assert window._countdown is None
    assert "localhost:8765/tok/" in window.phone_status.text()

    _all_green(window, state, qtbot)
    assert window.all_green()
    assert window._countdown == AUTO_START_S
    assert "Empieza en 10 s" in window.phone_payload()["hint"]
    for _ in range(AUTO_START_S - 1):
        state.snapshot(None, awake=True)
        window._tick()
        assert not started
    state.snapshot(None, awake=True)
    window._tick()
    assert len(started) == 1


def test_touching_the_window_cancels_auto_start(make_setup: Any, qtbot: Any) -> None:
    phone, state = _phone()
    window = make_setup(phone=phone)
    started: list[Any] = []
    window.start_requested.connect(started.append)
    _all_green(window, state, qtbot)
    assert window._countdown == AUTO_START_S
    qtbot.mouseClick(window.api_key, Qt.MouseButton.LeftButton)
    assert window._countdown is None
    for _ in range(AUTO_START_S + 2):
        state.snapshot(None, awake=True)
        window._tick()
    assert not started
    assert "cancelado" in window.countdown_label.text()


def test_missing_key_is_red_and_reported_on_phone(
    make_setup: Any, setup_cfg: AppConfig, qtbot: Any
) -> None:
    phone, _state = _phone()
    cfg = replace(setup_cfg, gemini=replace(setup_cfg.gemini, api_key=""))
    window = make_setup(cfg, phone=phone)
    qtbot.waitUntil(lambda: window.check_state("Gemini") is False, timeout=5000)
    payload = window.phone_payload()
    assert "Revisa la pantalla de inicio del PC2" in payload["alert"]
    assert "falta la clave" in payload["alert"]

    window.api_key.setText("AIza-ya")
    window._gemini_edited()
    window.check_gemini()
    qtbot.waitUntil(lambda: window.check_state("Gemini") is True, timeout=5000)


def test_gemini_check_failure_is_shown(make_setup: Any, qtbot: Any) -> None:
    FakeAsker.fail_check = "La API key no es válida"
    window = make_setup()
    qtbot.waitUntil(lambda: window.check_state("Gemini") is False, timeout=5000)
    assert "no es válida" in window.check_labels["Gemini"].text()


def test_keys_received_and_models_loaded(make_setup: Any, qtbot: Any) -> None:
    window = make_setup()
    window.mark_preset_received(1)
    window.mark_action_received("scroll")
    window.mark_preset_received(99)  # no existe: no pasa nada
    assert "recibida" in window.rows[1].received.text()
    assert "recibida" in window.scroll_received.text()
    assert window.rows[0].received.text() == ""

    window.load_account_models()
    qtbot.waitUntil(lambda: window.model.findText("gemini-9-pro") >= 0, timeout=5000)


def test_test_question_shows_answer_and_reaches_phone(make_setup: Any, qtbot: Any) -> None:
    phone, _state = _phone()
    window = make_setup(phone=phone)
    window.ask_test_question()
    qtbot.waitUntil(lambda: "Respondió en" in window.test_result.text(), timeout=5000)
    assert "Uno" in window.test_result.text()
    card = window.phone_payload()["cards"][0]
    assert card["title"] == "Explícame esto"
    assert "<b>Uno</b>" in card["html"]
    assert card["done"] is True


# ---------------------------------------------------------------- controlador de la app
class FakeListener:
    last: ClassVar[Any] = None

    def __init__(self, on_press: Any, on_release: Any) -> None:
        self.on_press = on_press
        self.on_release = on_release
        FakeListener.last = self

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


def _key(name: str) -> Any:
    return SimpleNamespace(name=name)


def test_app_switches_between_setup_and_main(
    qtbot: Any, tmp_path: Path, setup_cfg: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_module, "find_adb", lambda _path="": None)
    capturaia = CapturaApp(
        setup_cfg,
        asker_factory=FakeAsker,
        phone=False,
        keyboard_module=SimpleNamespace(Listener=FakeListener),
        window_kwargs={
            "thread_pool": QThreadPool(),
            "history": History(None),
            "settings": QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat),
        },
    )
    setup = capturaia.show_setup(auto_start=False)
    setup._refresh_timer.stop()
    assert setup.check_state("Teclas") is True

    FakeListener.last.on_press(_key("f9"))  # en la pantalla de inicio solo marca la tecla
    FakeListener.last.on_release(_key("f9"))
    qtbot.waitUntil(lambda: "recibida" in setup.rows[1].received.text(), timeout=2000)

    setup.save_and_start(confirm=False)
    main = capturaia.main
    assert main is not None
    assert capturaia.setup is None

    FakeListener.last.on_press(_key("f8"))  # en la app, pregunta de verdad
    FakeListener.last.on_release(_key("f8"))
    qtbot.waitUntil(lambda: bool(main.panel.cards) and main.panel.cards[0].done, timeout=5000)
    assert main.panel.cards[0].text == "- **Uno**\n- Dos"

    main.setup_requested.emit()  # Archivo ▸ Pantalla de inicio
    assert capturaia.main is None
    assert capturaia.setup is not None
    assert not capturaia.setup._auto_start  # al volver a propósito, sin cuenta atrás
    capturaia.setup.close()
    capturaia.shutdown()
