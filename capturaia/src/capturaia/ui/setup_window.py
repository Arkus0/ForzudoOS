"""Pantalla de inicio: clave y modelo de Gemini, preguntas y teclas, capturadora, móvil,
comprobaciones y botón de empezar (o arranque solo si todo está en verde)."""

from __future__ import annotations

import functools
import time
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import datetime
from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from capturaia.capture import FrameSource, create_source, list_devices
from capturaia.config import (
    AppConfig,
    CaptureConfig,
    ConfigError,
    GeminiConfig,
    Preset,
    save_config,
)
from capturaia.gemini import Asker, GeminiClient, GeminiError
from capturaia.hotkeys import parse_hotkey
from capturaia.imaging import qimage_to_jpeg
from capturaia.phone import PhoneServer, markdown_to_html
from capturaia.ui.key_capture import KeyCaptureButton
from capturaia.ui.phone_dialog import PairDialog, PhoneDialog
from capturaia.worker import AskWorker

AUTO_START_S = 10
SIGNAL_GRACE_S = 3.0
RECOMMENDED_MODELS = (
    ("gemini-3.8-flash", "recomendado"),
    ("gemini-flash-latest", "siempre el Flash más nuevo"),
    ("gemini-3.5-flash-lite", "más rápido y barato"),
)
CHECKS = ("Capturadora", "Gemini", "Teclas", "Móvil", "Pantalla del móvil")
COLORS = {True: "#3fb950", False: "#f85149", None: "#8b949e"}
PLATFORM_TOOLS_URL = "https://developer.android.com/tools/releases/platform-tools"

AskerFactory = Callable[[GeminiConfig], Asker]


class PresetRow(QFrame):
    """Una pregunta: nombre, tecla, texto de la pregunta y marca de «tecla recibida»."""

    remove_requested = Signal(object)
    key_changed = Signal()

    def __init__(self, preset: Preset) -> None:
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        grid = QGridLayout(self)
        self.name = QLineEdit(preset.name)
        self.name.setPlaceholderText("Nombre (p. ej. Explícame esto)")
        self.key = KeyCaptureButton(preset.hotkey)
        self.key.changed.connect(lambda _k: self.key_changed.emit())
        self.received = QLabel("")
        self.remove = QToolButton()
        self.remove.setText("Quitar")
        self.remove.clicked.connect(lambda: self.remove_requested.emit(self))
        self.prompt = QPlainTextEdit(preset.prompt)
        self.prompt.setPlaceholderText("Qué le pides a Gemini sobre lo que se ve en pantalla")
        self.prompt.setFixedHeight(56)
        grid.addWidget(self.name, 0, 0)
        grid.addWidget(self.key, 0, 1)
        grid.addWidget(self.received, 0, 2)
        grid.addWidget(self.remove, 0, 3)
        grid.addWidget(self.prompt, 1, 0, 1, 4)
        grid.setColumnStretch(0, 1)

    def preset(self) -> Preset:
        return Preset(
            name=self.name.text().strip(),
            prompt=self.prompt.toPlainText().strip(),
            hotkey=self.key.hotkey,
        )

    def mark_received(self) -> None:
        self.received.setText(f'<span style="color:{COLORS[True]}">✓ recibida</span>')


class _InteractionWatcher(QObject):
    """Cualquier clic o tecla en la ventana cancela el arranque automático."""

    def __init__(self, callback: Callable[[], None]) -> None:
        super().__init__()
        self._callback = callback

    def eventFilter(self, _obj: QObject, event: QEvent) -> bool:
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress):
            self._callback()
        return False


class SetupWindow(QWidget):
    start_requested = Signal(object)  # AppConfig ya guardada
    keys_changed = Signal()  # el controlador rehace las teclas globales
    adb_search_requested = Signal()

    def __init__(
        self,
        config: AppConfig,
        *,
        phone: PhoneServer | None = None,
        source_factory: Callable[[CaptureConfig, str], FrameSource] = create_source,
        device_lister: Callable[[CaptureConfig], list[str]] = list_devices,
        asker_factory: AskerFactory | None = None,
        thread_pool: QThreadPool | None = None,
        auto_start: bool = True,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__()
        self._config = config
        self._phone = phone
        self._source_factory = source_factory
        self._asker_factory: AskerFactory = asker_factory or GeminiClient
        self._pool = thread_pool or QThreadPool.globalInstance()
        self._workers: dict[int, AskWorker] = {}
        self._next_worker = 1
        self._clock = clock
        self._source: FrameSource | None = None
        self._source_started = clock()
        self._checks: dict[str, tuple[bool | None, str]] = {n: (None, "…") for n in CHECKS}
        self._adb = ""
        self._usb_base = ""
        self._usb_status = ""
        self._auto_start = auto_start
        self._countdown: int | None = None
        self._test_card: dict[str, Any] | None = None
        self._gemini_generation = 0
        self._closed = False  # las respuestas que lleguen tarde ya no tocan la ventana

        self.setWindowTitle("CapturaIA · Pantalla de inicio")
        self.resize(980, 900)
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        self._body = QVBoxLayout(body)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        self._body.addWidget(self._build_gemini())
        self._body.addWidget(self._build_presets())
        self._body.addWidget(self._build_capture(device_lister(config.capture)))
        self._body.addWidget(self._build_phone())
        self._body.addWidget(self._build_checks())
        self._body.addStretch(1)
        outer.addWidget(self._build_footer())

        self._watcher = _InteractionWatcher(self.cancel_auto_start)
        self.installEventFilter(self._watcher)
        for child in self.findChildren(QWidget):
            child.installEventFilter(self._watcher)

        self._setup_timers()

        if not auto_start:
            self.countdown_label.setText("Pulsa «Guardar y empezar» cuando quieras.")
        self._start_source(self.device_combo.currentText())
        QTimer.singleShot(0, self.check_gemini)

    def _setup_timers(self) -> None:
        self._gemini_timer = QTimer(self)
        self._gemini_timer.setSingleShot(True)
        self._gemini_timer.setInterval(900)  # espera a que termines de escribir la clave
        self._gemini_timer.timeout.connect(self.check_gemini)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(1000)
        self._refresh_timer.timeout.connect(self._tick)
        self._refresh_timer.start()

    # ------------------------------------------------------------------ secciones
    def _build_gemini(self) -> QGroupBox:
        box = QGroupBox("1. Gemini")
        grid = QGridLayout(box)
        self.api_key = QLineEdit(self._config.gemini.api_key)
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("Pega aquí tu clave de Gemini")
        self.api_key.textEdited.connect(self._gemini_edited)
        show = QCheckBox("Mostrar")
        show.toggled.connect(
            lambda on: self.api_key.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )
        link = QLabel('<a href="https://aistudio.google.com/apikey">Conseguir una clave gratis</a>')
        link.setOpenExternalLinks(True)
        grid.addWidget(QLabel("Clave"), 0, 0)
        grid.addWidget(self.api_key, 0, 1)
        grid.addWidget(show, 0, 2)
        grid.addWidget(link, 0, 3)

        self.model = QComboBox()
        self.model.setEditable(True)
        for name, note in RECOMMENDED_MODELS:
            self.model.addItem(name)
            self.model.setItemData(self.model.count() - 1, note, Qt.ItemDataRole.ToolTipRole)
        self.model.setCurrentText(self._config.gemini.model)
        self.model.currentTextChanged.connect(self._gemini_edited)
        self.load_models = QPushButton("Cargar modelos de mi cuenta")
        self.load_models.clicked.connect(self.load_account_models)
        notes = " · ".join(f"{n}: {d}" for n, d in RECOMMENDED_MODELS)
        model_help = QLabel(notes)
        model_help.setWordWrap(True)
        model_help.setStyleSheet("color: palette(placeholder-text);")
        grid.addWidget(QLabel("Modelo"), 1, 0)
        grid.addWidget(self.model, 1, 1)
        grid.addWidget(self.load_models, 1, 2, 1, 2)
        grid.addWidget(model_help, 2, 1, 1, 3)
        grid.setColumnStretch(1, 1)
        return box

    def _build_presets(self) -> QGroupBox:
        box = QGroupBox("2. Preguntas y teclas")
        layout = QVBoxLayout(box)
        tip = QLabel(
            "Pulsa el botón de la tecla y después la tecla o el botón del mando. "
            "Cuando pulses una tecla ya asignada, su fila marcará «✓ recibida»: así compruebas "
            "el mando."
        )
        tip.setWordWrap(True)
        layout.addWidget(tip)
        self._rows_box = QVBoxLayout()
        layout.addLayout(self._rows_box)
        self.rows: list[PresetRow] = []
        for preset in self._config.presets:
            self._add_row(preset)
        add = QPushButton("Añadir pregunta")
        add.clicked.connect(lambda: self._add_row(Preset(name="", prompt="", hotkey="")))
        layout.addWidget(add, 0, Qt.AlignmentFlag.AlignLeft)

        other = QGridLayout()
        presenter = self._config.presenter
        self.scroll_key = KeyCaptureButton(presenter.scroll_hotkey)
        self.toggle_key = KeyCaptureButton(presenter.toggle_hotkey)
        self.scroll_received = QLabel("")
        self.toggle_received = QLabel("")
        for button in (self.scroll_key, self.toggle_key):
            button.changed.connect(lambda _k: self.keys_changed.emit())
        other.addWidget(QLabel("Pasar página en el móvil"), 0, 0)
        other.addWidget(self.scroll_key, 0, 1)
        other.addWidget(self.scroll_received, 0, 2)
        other.addWidget(QLabel("Modo atril (monitor del PC2)"), 1, 0)
        other.addWidget(self.toggle_key, 1, 1)
        other.addWidget(self.toggle_received, 1, 2)
        other.setColumnStretch(2, 1)
        layout.addWidget(QLabel("<b>Otras teclas</b>"))
        layout.addLayout(other)
        return box

    def _add_row(self, preset: Preset) -> PresetRow:
        row = PresetRow(preset)
        row.remove_requested.connect(self._remove_row)
        row.key_changed.connect(self.keys_changed.emit)
        if hasattr(self, "_watcher"):  # filas añadidas después de construir la ventana
            for widget in [row, *row.findChildren(QWidget)]:
                widget.installEventFilter(self._watcher)
        self.rows.append(row)
        self._rows_box.addWidget(row)
        self.keys_changed.emit()
        return row

    def _remove_row(self, row: PresetRow) -> None:
        if row in self.rows:
            self.rows.remove(row)
            row.setParent(None)
            row.deleteLater()
            self.keys_changed.emit()

    def _build_capture(self, devices: list[str]) -> QGroupBox:
        box = QGroupBox("3. Capturadora")
        layout = QHBoxLayout(box)
        left = QVBoxLayout()
        self.device_combo = QComboBox()
        if self._config.capture.backend == "image":
            self.device_combo.addItem("Imagen de prueba")
            self.device_combo.setEnabled(False)
        else:
            self.device_combo.addItems(devices)
            wanted = self._config.capture.device
            if wanted and wanted not in devices:
                self.device_combo.insertItem(0, wanted)
            if wanted:
                self.device_combo.setCurrentText(wanted)
        self.device_combo.currentTextChanged.connect(self._start_source)
        self.capture_status = QLabel("…")
        self.capture_status.setWordWrap(True)
        left.addWidget(QLabel("Dispositivo"))
        left.addWidget(self.device_combo)
        left.addWidget(self.capture_status)
        left.addStretch(1)
        self._preview = QWidget()
        self._preview.setFixedSize(320, 180)
        self._preview.setStyleSheet("background: black;")
        self._preview_layout = QVBoxLayout(self._preview)
        self._preview_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(left, 1)
        layout.addWidget(self._preview)
        return box

    def _build_phone(self) -> QGroupBox:
        box = QGroupBox("4. Móvil")
        layout = QVBoxLayout(box)
        self.phone_status = QLabel("…")
        self.phone_status.setWordWrap(True)
        self.phone_status.setTextFormat(Qt.TextFormat.RichText)
        self.phone_status.setOpenExternalLinks(True)
        layout.addWidget(self.phone_status)
        buttons = QHBoxLayout()
        self.pair_button = QPushButton("Emparejar sin cable…")
        self.pair_button.clicked.connect(self.show_pair_dialog)
        self.qr_button = QPushButton("Código QR para abrir la página…")
        self.qr_button.clicked.connect(self.show_phone_dialog)
        self.find_adb_button = QPushButton("Buscar adb de nuevo")
        self.find_adb_button.clicked.connect(self.adb_search_requested.emit)
        for button in (self.pair_button, self.qr_button, self.find_adb_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.qr_button.setEnabled(self._phone is not None)
        self.pair_button.setEnabled(False)
        return box

    def _build_checks(self) -> QGroupBox:
        box = QGroupBox("5. Comprobación")
        layout = QVBoxLayout(box)
        self.check_labels: dict[str, QLabel] = {}
        grid = QGridLayout()
        for i, name in enumerate(CHECKS):
            label = QLabel()
            label.setWordWrap(True)
            self.check_labels[name] = label
            grid.addWidget(label, i, 0)
        layout.addLayout(grid)
        buttons = QHBoxLayout()
        check_all = QPushButton("Comprobar todo")
        check_all.clicked.connect(self.check_all)
        self.test_button = QPushButton("Pregunta de prueba")
        self.test_button.setToolTip("Manda la imagen actual con la primera pregunta")
        self.test_button.clicked.connect(self.ask_test_question)
        buttons.addWidget(check_all)
        buttons.addWidget(self.test_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.test_result = QLabel("")
        self.test_result.setWordWrap(True)
        self.test_result.setTextFormat(Qt.TextFormat.MarkdownText)
        self.test_result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.test_result)
        self._render_checks()
        return box

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        layout = QHBoxLayout(footer)
        self.countdown_label = QLabel("")
        self.stay_button = QPushButton("Quedarme aquí")
        self.stay_button.clicked.connect(self.cancel_auto_start)
        self.stay_button.hide()
        self.start_button = QPushButton("Guardar y empezar")
        self.start_button.setDefault(True)
        self.start_button.setMinimumHeight(40)
        self.start_button.setStyleSheet("font-weight: bold; padding: 0 24px;")
        self.start_button.clicked.connect(self.save_and_start)
        layout.addWidget(self.countdown_label, 1)
        layout.addWidget(self.stay_button)
        layout.addWidget(self.start_button)
        return footer

    # ------------------------------------------------------------------ capturadora
    def _start_source(self, device: str) -> None:
        self._stop_source()
        source = self._source_factory(self._config.capture, device)
        widget = source.preview_widget()
        widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self._preview_layout.addWidget(widget)
        self._source = source
        self._source_started = self._clock()
        source.error.connect(self.capture_status.setText)
        source.status.connect(self.capture_status.setText)
        source.start()

    def _stop_source(self) -> None:
        if self._source is not None:
            self._source.stop()
            widget = self._source.preview_widget()
            self._preview_layout.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()
            self._source.deleteLater()
            self._source = None

    # ------------------------------------------------------------------ móvil
    def set_usb(self, adb: str, url_base: str) -> None:
        self._adb = adb
        self._usb_base = url_base
        self.pair_button.setEnabled(bool(adb))
        self.find_adb_button.setVisible(not adb)
        self._render_phone()

    def set_usb_status(self, message: str, _ok: object = None) -> None:
        self._usb_status = message
        self._render_phone()

    @property
    def phone_usb_url(self) -> str:
        if not self._usb_base or self._phone is None:
            return ""
        return f"{self._usb_base}/{self._phone.token}/"

    def show_pair_dialog(self) -> None:
        if self._adb:
            PairDialog(self._adb, self).exec()

    def show_phone_dialog(self) -> None:
        if self._phone is not None:
            PhoneDialog(
                self._phone.url, self, usb_url=self.phone_usb_url, usb_status=self._usb_status
            ).exec()

    def _render_phone(self) -> None:
        if self._phone is None:
            self.phone_status.setText("La página del móvil está desactivada ([phone] enabled).")
            return
        lines = []
        if self._adb:
            lines.append(f"adb: encontrado. {self._usb_status or 'Buscando el móvil…'}")
            lines.append(f"Dirección en el móvil: <b>{self.phone_usb_url}</b>")
        else:
            lines.append(
                "adb no encontrado: para usar el móvil emparejado (sin IP fija), descomprime "
                f'<a href="{PLATFORM_TOOLS_URL}">SDK Platform-Tools for Windows</a> dentro de '
                "la carpeta capturaia y pulsa «Buscar adb de nuevo»."
            )
            lines.append(f"Mientras, por wifi: <b>{self._phone.url}</b>")
        self.phone_status.setText("<br>".join(lines))

    # ------------------------------------------------------------------ teclas
    def presets_for_hotkeys(self) -> list[Preset]:
        return [row.preset() for row in self.rows]

    def actions_for_hotkeys(self) -> dict[str, str]:
        return {"presenter": self.toggle_key.hotkey, "scroll": self.scroll_key.hotkey}

    def mark_preset_received(self, index: int) -> None:
        if 0 <= index < len(self.rows):
            self.rows[index].mark_received()

    def mark_action_received(self, name: str) -> None:
        label = {"scroll": self.scroll_received, "presenter": self.toggle_received}.get(name)
        if label is not None:
            label.setText(f'<span style="color:{COLORS[True]}">✓ recibida</span>')

    def set_hotkeys_status(self, ok: bool, detail: str) -> None:
        self._set_check("Teclas", ok, detail)

    # ------------------------------------------------------------------ comprobaciones
    def _set_check(self, name: str, ok: bool | None, detail: str) -> None:
        if self._closed:
            return
        self._checks[name] = (ok, detail)
        self._render_checks()

    def check_state(self, name: str) -> bool | None:
        return self._checks[name][0]

    def all_green(self) -> bool:
        return all(ok is True for ok, _ in self._checks.values())

    def _render_checks(self) -> None:
        for name, (ok, detail) in self._checks.items():
            dot = f'<span style="color:{COLORS[ok]}; font-size: 16pt">●</span>'
            self.check_labels[name].setText(f"{dot} <b>{name}</b>: {detail}")

    def _gemini_edited(self, *_args: object) -> None:
        self._gemini_generation += 1
        self._set_check("Gemini", None, "comprobando…")
        self._gemini_timer.start()

    def _current_gemini(self) -> GeminiConfig:
        return replace(
            self._config.gemini,
            api_key=self.api_key.text().strip(),
            model=self.model.currentText().strip(),
        )

    def _make_asker(self) -> Asker:
        gemini = self._current_gemini()
        if not gemini.resolved_api_key():
            msg = "falta la clave: pégala arriba (es gratis, ver enlace)"
            raise GeminiError(msg)
        return self._asker_factory(gemini)

    def check_gemini(self) -> None:
        generation = self._gemini_generation
        try:
            asker = self._make_asker()
        except GeminiError as exc:
            self._set_check("Gemini", False, str(exc))
            return
        check = getattr(asker, "check", None)
        if check is None:
            self._set_check("Gemini", True, asker.model)
            return
        self._set_check("Gemini", None, "comprobando…")

        def run() -> Iterator[str]:
            yield check()

        def done(_id: int, name: str, _s: float) -> None:
            if generation == self._gemini_generation:  # ignora comprobaciones antiguas
                self._set_check("Gemini", True, f"clave válida · {name}")

        def failed(_id: int, message: str) -> None:
            if generation == self._gemini_generation:
                self._set_check("Gemini", False, message)

        worker = AskWorker(0, run)
        worker.signals.finished.connect(done)
        worker.signals.failed.connect(failed)
        self._start_worker(worker)

    def load_account_models(self) -> None:
        try:
            asker = self._make_asker()
        except GeminiError as exc:
            QMessageBox.warning(self, "Modelos", str(exc))
            return
        lister = getattr(asker, "list_models", None)
        if lister is None:
            return

        def run() -> Iterator[str]:
            yield "\n".join(lister())

        def done(_id: int, text: str, _s: float) -> None:
            if self._closed:
                return
            current = self.model.currentText()
            known = {self.model.itemText(i) for i in range(self.model.count())}
            for name in text.splitlines():
                if name and name not in known:
                    self.model.addItem(name)
            self.model.setCurrentText(current)
            self.load_models.setText(f"Cargados {len(text.splitlines())} modelos")

        worker = AskWorker(0, run)
        worker.signals.finished.connect(done)
        worker.signals.failed.connect(lambda _id, msg: QMessageBox.warning(self, "Modelos", msg))
        self._start_worker(worker)

    def check_all(self) -> None:
        self.check_gemini()
        self.keys_changed.emit()
        self._tick()

    def _tick(self) -> None:
        """Cada segundo: capturadora, móvil, publicación al móvil y cuenta atrás."""
        self._check_capture()
        self._check_phone()
        self._publish_to_phone()
        self._advance_countdown()

    def _check_capture(self) -> None:
        if self._source is None:
            self._set_check("Capturadora", False, "sin dispositivo")
            return
        fps = self._source.measured_fps()
        size = self._source.frame_size()
        if fps is None:
            self._set_check("Capturadora", True, "imagen fija de prueba")
        elif fps >= 0.5:
            res = f"{size.width()}x{size.height()} · " if size is not None else ""
            self._set_check("Capturadora", True, f"{res}{fps:.0f} fps")
        elif self._clock() - self._source_started < SIGNAL_GRACE_S:
            self._set_check("Capturadora", None, "abriendo…")
        else:
            self._set_check(
                "Capturadora", False, "no llega imagen (¿capturadora conectada y elegida?)"
            )

    def _check_phone(self) -> None:
        self._render_phone()
        if self._phone is None:
            self._set_check("Móvil", True, "desactivado")
            self._set_check("Pantalla del móvil", True, "—")
            return
        connected = self._phone.state.connected()
        if connected:
            how = "por localhost" if self._usb_status.startswith("Móvil conectado") else ""
            self._set_check("Móvil", True, f"leyendo la página {how}".strip())
        else:
            self._set_check("Móvil", False, "abre la página en el móvil (botón del código QR)")
        awake = self._phone.state.phone_awake()
        if awake:
            self._set_check("Pantalla del móvil", True, "no se apagará")
        elif awake is False:
            self._set_check(
                "Pantalla del móvil",
                False,
                "puede apagarse: toca la pantalla del móvil una vez (o ábrela por localhost)",
            )
        else:
            self._set_check("Pantalla del móvil", False, "esperando al móvil")

    # ------------------------------------------------------------------ pregunta de prueba
    def ask_test_question(self) -> None:
        frame = self._source.grab_frame() if self._source is not None else None
        if frame is None:
            self.test_result.setText("No hay imagen de la capturadora todavía.")
            return
        presets = [p for p in self.presets_for_hotkeys() if p.prompt]
        prompt = presets[0].prompt if presets else "Describe lo que ves."
        title = presets[0].name if presets else "Prueba"
        try:
            asker = self._make_asker()
            jpeg = qimage_to_jpeg(
                frame, self._config.capture.jpeg_quality, self._config.capture.max_width
            )
        except (GeminiError, ValueError, RuntimeError) as exc:
            self.test_result.setText(f"No se pudo preguntar: {exc}")
            return
        self.test_result.setText("Pensando…")
        card: dict[str, Any] = {
            "id": f"setup-{datetime.now():%H%M%S%f}",
            "title": title,
            "html": "",
            "status": "Pensando…",
            "error": False,
            "done": False,
        }
        self._test_card = card
        parts: list[str] = []

        def chunk(_id: int, text: str) -> None:
            parts.append(text)
            card["html"] = markdown_to_html("".join(parts))
            if not self._closed:
                self.test_result.setText("".join(parts))

        def done(_id: int, text: str, seconds: float) -> None:
            card.update(html=markdown_to_html(text), status=f"{seconds:.1f} s", done=True)
            if not self._closed:
                self.test_result.setText(f"{text}\n\n*Respondió en {seconds:.1f} s.*")
            self._set_check("Gemini", True, f"respondió en {seconds:.1f} s")

        def failed(_id: int, message: str) -> None:
            card.update(html=message, error=True, done=True)
            self._set_check("Gemini", False, message)
            if not self._closed:
                self.test_result.setText(f"Error: {message}")

        worker = AskWorker(0, functools.partial(asker.ask_stream, jpeg, prompt))
        worker.signals.chunk.connect(chunk)
        worker.signals.finished.connect(done)
        worker.signals.failed.connect(failed)
        self._start_worker(worker)

    def _start_worker(self, worker: AskWorker) -> None:
        worker.setAutoDelete(False)
        key = self._next_worker
        self._next_worker += 1
        self._workers[key] = worker

        def release(*_args: object) -> None:
            QTimer.singleShot(0, lambda: self._workers.pop(key, None))

        worker.signals.finished.connect(release)
        worker.signals.failed.connect(release)
        self._pool.start(worker)

    # ------------------------------------------------------------------ móvil: estado
    def phone_payload(self) -> dict[str, Any]:
        problems = [
            f"{name} ({detail})"
            for name, (ok, detail) in self._checks.items()
            if ok is False and name not in ("Móvil", "Pantalla del móvil")
        ]
        if self._countdown is not None:
            hint = f"Todo listo. Empieza en {self._countdown} s…"
        else:
            hint = "Pantalla de inicio del PC2: comprobando…"
        return {
            "cards": [self._test_card] if self._test_card else [],
            "health": {name: ok for name, (ok, _d) in self._checks.items()},
            "alert": "Revisa la pantalla de inicio del PC2: " + "; ".join(problems)
            if problems
            else "",
            "hint": hint,
            "page": 0,
        }

    def _publish_to_phone(self) -> None:
        if self._phone is not None:
            self._phone.state.publish(self.phone_payload())

    # ------------------------------------------------------------------ empezar
    def cancel_auto_start(self) -> None:
        if self._auto_start:
            self._auto_start = False
            self._countdown = None
            self.stay_button.hide()
            self.countdown_label.setText(
                "Arranque automático cancelado. Pulsa «Guardar y empezar»."
            )

    def _advance_countdown(self) -> None:
        if not self._auto_start:
            return
        if not self.all_green():
            self._countdown = None
            self.stay_button.hide()
            self.countdown_label.setText("Esperando a que todo esté en verde…")
            return
        self._countdown = AUTO_START_S if self._countdown is None else self._countdown - 1
        if self._countdown <= 0:
            self._countdown = None
            self.save_and_start(confirm=False)
            return
        self.stay_button.show()
        self.countdown_label.setText(f"<b>Todo listo: empieza sola en {self._countdown} s</b>")

    def collect_config(self) -> AppConfig:
        """Configuración con lo que hay en pantalla. Lanza ConfigError si algo no vale."""
        presets = tuple(row.preset() for row in self.rows)
        if not presets:
            msg = "Añade al menos una pregunta."
            raise ConfigError(msg)
        seen: dict[frozenset[str], str] = {}
        labelled = [(p.hotkey, f"«{p.name or 'sin nombre'}»") for p in presets]
        labelled += [
            (self.scroll_key.hotkey, "«Pasar página»"),
            (self.toggle_key.hotkey, "«Modo atril»"),
        ]
        for i, preset in enumerate(presets, start=1):
            if not preset.name or not preset.prompt:
                msg = f"La pregunta nº {i} necesita nombre y texto."
                raise ConfigError(msg)
        for hotkey, label in labelled:
            if not hotkey:
                continue
            combo = parse_hotkey(hotkey)
            if combo in seen:
                msg = f"La tecla de {label} ya la usa {seen[combo]}."
                raise ConfigError(msg)
            seen[combo] = label
        model = self.model.currentText().strip()
        if not model:
            msg = "Elige un modelo de Gemini."
            raise ConfigError(msg)
        device = self._config.capture.device
        if self._config.capture.backend != "image":
            device = self.device_combo.currentText()
        return replace(
            self._config,
            gemini=self._current_gemini(),
            presets=presets,
            capture=replace(self._config.capture, device=device),
            presenter=replace(
                self._config.presenter,
                scroll_hotkey=self.scroll_key.hotkey,
                toggle_hotkey=self.toggle_key.hotkey,
            ),
        )

    def save_and_start(self, *, confirm: bool = True) -> AppConfig | None:
        try:
            cfg = self.collect_config()
            if cfg.path is not None:
                save_config(cfg)
        except (ConfigError, OSError) as exc:
            self.cancel_auto_start()
            QMessageBox.warning(self, "No se puede empezar", str(exc))
            return None
        if confirm and not self.all_green():
            pending = ", ".join(n for n, (ok, _d) in self._checks.items() if ok is not True)
            answer = QMessageBox.question(
                self,
                "Empezar",
                f"Hay comprobaciones sin verde ({pending}). ¿Empezar igualmente?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return None
        self._shutdown()
        self.start_requested.emit(cfg)
        return cfg

    def _shutdown(self) -> None:
        self._closed = True
        self._refresh_timer.stop()
        self._gemini_timer.stop()
        self._stop_source()

    def closeEvent(self, event: Any) -> None:
        self._shutdown()
        super().closeEvent(event)
