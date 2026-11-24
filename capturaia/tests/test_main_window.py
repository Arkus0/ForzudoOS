from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QSettings, QThreadPool

from capturaia.config import AppConfig
from capturaia.gemini import GeminiError
from capturaia.history import History
from capturaia.ui.main_window import MainWindow


class FakeAsker:
    model = "fake-model"

    def __init__(self, pieces: list[str] | None = None, error: str | None = None) -> None:
        self.pieces = pieces if pieces is not None else ["**Hola**", " mundo"]
        self.error = error
        self.calls: list[tuple[bytes, str]] = []
        self.gate = threading.Event()
        self.gate.set()

    def ask_stream(self, jpeg: bytes, prompt: str) -> Iterator[str]:
        self.calls.append((jpeg, prompt))
        self.gate.wait(5)
        if self.error:
            raise GeminiError(self.error)
        yield from self.pieces


@pytest.fixture
def window_factory(qtbot: Any, tmp_path: Path, config: AppConfig) -> Any:
    pools: list[QThreadPool] = []

    def make(asker: Any = None, **kwargs: Any) -> MainWindow:
        pool = QThreadPool()
        pools.append(pool)
        settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
        kwargs.setdefault("history", History(tmp_path / "capturas"))
        window = MainWindow(
            config,
            asker_factory=(lambda: asker) if asker is not None else None,
            thread_pool=pool,
            settings=settings,
            **kwargs,
        )
        qtbot.addWidget(window)
        return window

    yield make
    for pool in pools:
        pool.waitForDone(5000)


def test_ask_streams_answer_into_card_and_saves(
    window_factory: Any, qtbot: Any, tmp_path: Path
) -> None:
    asker = FakeAsker()
    window = window_factory(asker)
    assert window.ask(0) is not None
    card = window.panel.cards[0]
    qtbot.waitUntil(lambda: card.done, timeout=5000)

    assert card.text == "**Hola** mundo"
    assert card.status.text().startswith("Listo en")
    assert window.pending_requests == 0
    jpeg, prompt = asker.calls[0]
    assert jpeg[:2] == b"\xff\xd8"
    assert prompt == window._config.presets[0].prompt
    saved = sorted((tmp_path / "capturas").iterdir())
    assert [p.suffix for p in saved] == [".jpg", ".md"]
    assert "fake-model" in saved[1].read_text(encoding="utf-8")


def test_same_preset_is_not_relaunched_while_running(window_factory: Any, qtbot: Any) -> None:
    asker = FakeAsker()
    asker.gate.clear()
    window = window_factory(asker)
    assert window.ask(0) is not None
    assert window.ask(0) is None  # bloqueado: ya en curso
    assert window.ask(1) is not None  # otro preset sí puede
    assert len(window.panel.cards) == 2
    asker.gate.set()
    qtbot.waitUntil(lambda: window.pending_requests == 0, timeout=5000)
    assert window.ask(0) is not None  # liberado al terminar
    qtbot.waitUntil(lambda: window.pending_requests == 0, timeout=5000)


def test_gemini_error_shows_in_card(window_factory: Any, qtbot: Any, tmp_path: Path) -> None:
    window = window_factory(FakeAsker(error="cuota agotada"))
    window.ask(0)
    card = window.panel.cards[0]
    qtbot.waitUntil(lambda: card.done, timeout=5000)
    assert card.body.text() == "cuota agotada"
    assert card.status.text() == "Error"
    assert not (tmp_path / "capturas").exists()


def test_empty_answer_is_an_error(window_factory: Any, qtbot: Any) -> None:
    window = window_factory(FakeAsker(pieces=[]))
    window.ask(0)
    card = window.panel.cards[0]
    qtbot.waitUntil(lambda: card.done, timeout=5000)
    assert "no devolvió texto" in card.body.text()


def test_missing_api_key_error_card(window_factory: Any) -> None:
    window = window_factory(None)  # usa el GeminiClient real, sin clave
    assert window.ask(0) is None
    card = window.panel.cards[0]
    assert card.done
    assert "GEMINI_API_KEY" in card.body.text()


def test_custom_question(window_factory: Any, qtbot: Any) -> None:
    asker = FakeAsker()
    window = window_factory(asker)
    assert window.ask_custom() is None  # vacío: no hace nada
    window.custom_edit.setText("  ¿Cuánta vida me queda?  ")
    window.custom_edit.returnPressed.emit()
    qtbot.waitUntil(lambda: window.pending_requests == 0 and bool(asker.calls), timeout=5000)
    assert asker.calls[0][1] == "¿Cuánta vida me queda?"
    assert window.custom_edit.text() == ""


def test_no_frame_yet(window_factory: Any) -> None:
    window = window_factory(FakeAsker())
    window._source.grab_frame = lambda: None
    assert window.ask(0) is None
    assert window.panel.cards == []
    assert "imagen" in window.statusBar().currentMessage()


def test_toolbar_button_uses_selected_preset(window_factory: Any, qtbot: Any) -> None:
    asker = FakeAsker()
    window = window_factory(asker)
    window.preset_combo.setCurrentIndex(1)
    window.ask_button.click()
    qtbot.waitUntil(lambda: window.pending_requests == 0 and bool(asker.calls), timeout=5000)
    assert asker.calls[0][1] == window._config.presets[1].prompt
    assert window.ask(99) is None


def test_preview_toggle_and_clear(window_factory: Any, qtbot: Any) -> None:
    window = window_factory(FakeAsker())
    window.show()
    window.preview_action.setChecked(False)
    assert window._splitter.sizes()[0] == 0
    window.preview_action.setChecked(True)
    assert window._splitter.sizes()[0] > 0

    window.ask(0)
    qtbot.waitUntil(lambda: window.pending_requests == 0, timeout=5000)
    window.panel.clear()
    assert window.panel.cards == []


def test_local_shortcuts_registered(window_factory: Any) -> None:
    window = window_factory(FakeAsker())
    window.enable_local_shortcuts()
    keys = sorted(s.key().toString() for s in window._shortcuts)
    assert keys == ["F8", "F9"]
