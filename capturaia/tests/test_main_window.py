from __future__ import annotations

import threading
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QSettings, Qt, QThreadPool
from PySide6.QtWidgets import QLabel

from capturaia.capture.base import FrameSource
from capturaia.capture.image_source import demo_pattern
from capturaia.config import AppConfig
from capturaia.gemini import GeminiError
from capturaia.history import History
from capturaia.ui.layout import presenter_split
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
    qtbot.waitUntil(lambda: not window._workers, timeout=2000)  # no se acumulan workers
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
    assert "Sin señal" in window.statusBar().currentMessage()


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
    assert keys == ["F10", "F12", "F7", "F8", "F9"]


def _presenter_config(config: AppConfig, **changes: Any) -> AppConfig:
    return replace(config, presenter=replace(config.presenter, screen=0, **changes))


@pytest.mark.parametrize("side", ["right", "left"])
def test_presenter_mode_layout_and_exit(
    qtbot: Any, tmp_path: Path, config: AppConfig, side: str
) -> None:
    settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    cfg = _presenter_config(config, side=side, strip_width=200, font_size=26, show_video=True)
    window = MainWindow(cfg, asker_factory=FakeAsker, settings=settings)
    qtbot.addWidget(window)
    window.show()
    normal_sizes = window._splitter.sizes()

    window.handle_action("presenter")
    assert window.presenter_mode
    assert window.isFullScreen()
    assert not window.menuBar().isVisible()
    assert not window.statusBar().isVisible()
    assert window._splitter.handleWidth() == 0
    assert window.cursor().shape() == Qt.CursorShape.BlankCursor
    assert "F8 Explícame esto" in window.panel._empty.text()

    area = window._splitter.size()
    frame = window._source.frame_size()
    video_w, strip_w = presenter_split(
        area.width(), area.height(), frame.width(), frame.height(), 200
    )
    expected = [video_w, strip_w] if side == "right" else [strip_w, video_w]
    assert window._splitter.sizes() == expected
    first = window._splitter.widget(0)
    assert (first is window.panel) == (side == "left")

    # Las respuestas nuevas salen con letra grande y sin miniatura.
    window.ask(0)
    card = window.panel.cards[0]
    qtbot.waitUntil(lambda: card.done, timeout=5000)
    assert card.body.font().pointSizeF() == 26
    assert card.thumbnail.isHidden()
    assert card.property("latest")
    # La tarjeta nunca se sale de la franja (antes la línea de estado la ensanchaba).
    qtbot.waitUntil(lambda: card.width() <= window.panel._scroll.viewport().width(), timeout=2000)
    assert "guardado" not in card.status.text()

    window._exit_shortcut.activated.emit()  # Esc
    assert not window.presenter_mode
    assert not window.isFullScreen()
    assert window.menuBar().isVisible()
    assert window._splitter.widget(0) is window._preview_box
    # Se recupera el reparto normal (en proporción: la geometría puede ajustarse a la pantalla).
    sizes = window._splitter.sizes()
    assert sizes[0] / sum(sizes) == pytest.approx(normal_sizes[0] / sum(normal_sizes), abs=0.02)
    assert not card.thumbnail.isHidden()
    window._pool.waitForDone(5000)


def test_presenter_scroll_action(window_factory: Any, qtbot: Any) -> None:
    window = window_factory(FakeAsker(pieces=["- línea\n" * 200]))
    window.show()
    window.ask(0)
    qtbot.waitUntil(lambda: window.pending_requests == 0, timeout=5000)
    bar = window.panel._scroll.verticalScrollBar()
    qtbot.waitUntil(lambda: bar.maximum() > 0, timeout=5000)
    window.handle_action("scroll")
    assert bar.value() > 0
    bar.setValue(bar.maximum())
    window.handle_action("scroll")  # al final vuelve arriba
    assert bar.value() == 0
    window.handle_action("desconocida")  # no hace nada


def test_status_shows_measured_fps(window_factory: Any) -> None:
    window = window_factory(FakeAsker())
    window._source.measured_fps = lambda: 59.94
    window._refresh_stats()
    assert window._source_label.text().endswith("recibiendo 59.9 fps")


class FakeLiveSource(FrameSource):
    """Capturadora simulada: se controla cuántos fps "llegan"."""

    def __init__(self, fps: float = 60.0) -> None:
        super().__init__()
        self.fps = fps
        self.preview = True
        self.widget = QLabel("vídeo")
        self.image = demo_pattern(1280, 720)

    def preview_widget(self) -> QLabel:
        return self.widget

    def start(self) -> None:
        self.status.emit("Capturadora falsa")

    def stop(self) -> None:
        pass

    def grab_frame(self) -> Any:
        return self.image.copy()

    def frame_size(self) -> Any:
        return self.image.size()

    def measured_fps(self) -> float | None:
        return self.fps

    def set_preview_enabled(self, enabled: bool) -> None:
        self.preview = enabled


@pytest.fixture
def live_window(qtbot: Any, tmp_path: Path, config: AppConfig) -> Any:
    sources: list[FakeLiveSource] = []

    def factory(_cfg: Any, _device: str) -> FakeLiveSource:
        sources.append(FakeLiveSource())
        return sources[-1]

    cfg = _presenter_config(config)  # valores por defecto: modo atril, franja a la izquierda
    window = MainWindow(
        cfg,
        asker_factory=FakeAsker,
        source_factory=factory,
        thread_pool=QThreadPool(),
        history=History(None),
        settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat),
    )
    qtbot.addWidget(window)
    window.sources = sources
    yield window
    window._pool.waitForDone(5000)


def test_answers_only_mode(live_window: Any, qtbot: Any) -> None:
    window = live_window
    window.show()
    source = window.sources[-1]
    window.set_presenter_mode(True)
    assert not source.preview  # no se pinta la imagen del portátil...
    assert source.widget.isHidden()
    assert window._splitter.widget(0) is window.panel  # ...franja a la izquierda
    area = window._splitter.size().width()
    assert window._splitter.sizes() == [340, area - 340]

    window.ask(0)  # ...pero se sigue pudiendo capturar
    card = window.panel.cards[0]
    qtbot.waitUntil(lambda: card.done, timeout=5000)
    assert card.text == "**Hola** mundo"

    window.set_presenter_mode(False)
    assert source.preview
    assert not source.widget.isHidden()


def test_signal_watchdog_alerts_and_reconnects(live_window: Any) -> None:
    window = live_window
    now = [100.0]
    window._clock = lambda: now[0]
    window._last_reconnect = now[0]
    window._refresh_stats()
    assert window.panel.health("Señal") is True

    window.sources[-1].fps = 0.0  # se corta la imagen
    window._refresh_stats()
    assert window.panel.alert_text == ""  # margen de unos segundos antes de avisar
    now[0] += 3.5
    window._refresh_stats()
    assert window.panel.health("Señal") is False
    assert "Sin señal" in window.panel.alert_text
    assert len(window.sources) == 1  # aún no toca reconectar

    # Sin señal no se envía nada (Gemini vería una imagen antigua).
    window.set_presenter_mode(True)
    assert window.ask(0) is None
    assert "Sin señal" in window.panel.cards[0].body.text()

    now[0] += 2
    window.sources[-1].fps = 0.0
    window._refresh_stats()
    assert len(window.sources) == 2  # reconectado
    assert not window.sources[-1].preview  # mantiene el modo atril

    window.sources[-1].fps = 59.9  # vuelve la imagen
    window._refresh_stats()
    assert window.panel.health("Señal") is True
    assert window.panel.alert_text == ""


class CheckingAsker(FakeAsker):
    def __init__(self, error: str | None = None) -> None:
        super().__init__()
        self.check_error = error

    def check(self) -> str:
        if self.check_error:
            raise GeminiError(self.check_error)
        return "Gemini Flash"


@pytest.mark.parametrize(("error", "ok"), [(None, True), ("clave no válida", False)])
def test_gemini_preflight(
    qtbot: Any, tmp_path: Path, config: AppConfig, error: str | None, ok: bool
) -> None:
    window = MainWindow(
        config,
        asker_factory=lambda: CheckingAsker(error),
        thread_pool=QThreadPool(),
        settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat),
    )
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: window.panel.health("Gemini") is ok, timeout=5000)
    if ok:
        assert window.panel.alert_text == ""
    else:
        assert "clave no válida" in window.panel.alert_text
    window._pool.waitForDone(5000)


def test_preflight_without_api_key(window_factory: Any, qtbot: Any) -> None:
    window = window_factory(None)
    qtbot.waitUntil(lambda: window.panel.health("Gemini") is False, timeout=5000)
    assert "GEMINI_API_KEY" in window.panel.alert_text
    window.set_hotkeys_health(True, "activas: F8")
    assert window.panel.health("Teclas") is True
