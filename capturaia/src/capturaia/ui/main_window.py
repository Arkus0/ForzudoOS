"""Ventana principal: vista previa de la capturadora + panel lateral de respuestas."""

from __future__ import annotations

import functools
import html
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QByteArray, QSettings, QSize, Qt, QThreadPool, QTimer, QUrl
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDesktopServices,
    QGuiApplication,
    QImage,
    QKeySequence,
    QResizeEvent,
    QShortcut,
)
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from capturaia.capture import FrameSource, create_source, list_devices
from capturaia.config import AppConfig, CaptureConfig
from capturaia.gemini import Asker, GeminiClient, GeminiError
from capturaia.history import History
from capturaia.hotkeys import pretty_hotkey
from capturaia.imaging import qimage_to_jpeg
from capturaia.phone import PhoneServer, markdown_to_html
from capturaia.ui.answer_panel import AnswerCard, AnswerPanel
from capturaia.ui.layout import presenter_split
from capturaia.ui.phone_dialog import PairDialog, PhoneDialog
from capturaia.worker import AskWorker

SourceFactory = Callable[[CaptureConfig, str], FrameSource]

NO_SIGNAL_GRACE_S = 3.0  # segundos sin imagen antes de avisar
RECONNECT_EVERY_S = 5.0  # cada cuánto se reintenta abrir la capturadora
MIN_LIVE_FPS = 0.5


@dataclass
class _Request:
    card: AnswerCard
    busy_key: int | None
    title: str
    prompt: str
    jpeg: bytes
    when: datetime
    model: str


class MainWindow(QMainWindow):
    def __init__(
        self,
        config: AppConfig,
        *,
        asker_factory: Callable[[], Asker] | None = None,
        history: History | None = None,
        source_factory: SourceFactory = create_source,
        device_lister: Callable[[CaptureConfig], list[str]] = list_devices,
        thread_pool: QThreadPool | None = None,
        settings: QSettings | None = None,
        phone: PhoneServer | None = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._asker_factory = asker_factory or (lambda: GeminiClient(config.gemini))
        self._asker: Asker | None = None
        self._history = history or History(config.history.folder, enabled=config.history.enabled)
        self._source_factory = source_factory
        self._pool = thread_pool or QThreadPool.globalInstance()
        self._requests: dict[int, _Request] = {}
        self._workers: dict[int, AskWorker] = {}
        self._next_worker_key = 1
        self._busy: dict[int, int] = {}  # preset -> id de la petición en curso
        self._next_id = 1
        self._source: FrameSource | None = None
        self._shortcuts: list[QShortcut] = []
        self._settings = settings or QSettings("CapturaIA", "CapturaIA")
        # El dispositivo del config manda; si está vacío, se recuerda el último elegido.
        self._initial_device = config.capture.device or str(self._settings.value("device", ""))

        self.setWindowTitle("CapturaIA")
        self.resize(1400, 820)

        first = config.presets[0]
        key_hint = f" ({pretty_hotkey(first.hotkey)})" if first.hotkey else ""
        self._normal_hint = (
            f"Pulsa «Preguntar»{key_hint} para enviar a Gemini lo que se ve ahora "
            "en la capturadora."
        )
        self.panel = AnswerPanel(self._normal_hint)
        self.presenter_mode = False
        self._saved_geometry: QByteArray | None = None
        self._saved_sizes: list[int] = []
        self._source_text = "Sin fuente"
        self._last_frame_size: QSize | None = None

        self._preview_box = QWidget()
        self._preview_layout = QVBoxLayout(self._preview_box)
        self._preview_layout.setContentsMargins(0, 0, 0, 0)
        self._preview_box.setStyleSheet("background: black;")

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._preview_box)
        self._splitter.addWidget(self.panel)
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 2)
        self._splitter.setSizes([880, 520])
        self._handle_width = self._splitter.handleWidth()
        self.setCentralWidget(self._splitter)

        self._build_toolbar(device_lister(config.capture))
        self._source_label = QLabel("Sin fuente")
        self.statusBar().addPermanentWidget(self._source_label)
        self._restore_window_geometry()

        if not config.gemini.resolved_api_key() and asker_factory is None:
            self.notify("Falta la API key de Gemini (variable GEMINI_API_KEY o config.toml).", 0)

        self._setup_timers_and_shortcuts()
        self._setup_phone(phone)
        self.start_source(self._initial_device)
        QTimer.singleShot(0, self.check_gemini)

    def _setup_timers_and_shortcuts(self) -> None:
        # Vigilancia de la señal de la capturadora (ver _watch_signal).
        self._current_device = ""
        self._clock: Callable[[], float] = time.monotonic
        self._no_signal_since: float | None = None
        self._last_reconnect = self._clock()

        self._exit_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._exit_shortcut.setEnabled(False)
        self._exit_shortcut.activated.connect(lambda: self.set_presenter_mode(False))

        # Cada segundo: fps recibidos en la barra de estado y reajuste si cambia la resolución.
        self._stats_timer = QTimer(self)
        self._stats_timer.setInterval(1000)
        self._stats_timer.timeout.connect(self._refresh_stats)
        self._stats_timer.start()

    # ------------------------------------------------------------------ interfaz
    def _build_toolbar(self, devices: list[str]) -> None:
        bar = QToolBar("Principal")
        bar.setMovable(False)
        self.addToolBar(bar)

        bar.addWidget(QLabel(" Fuente: "))
        self.device_combo = self._build_device_combo(devices)
        bar.addWidget(self.device_combo)
        bar.addSeparator()

        self.preset_combo = QComboBox()
        for preset in self._config.presets:
            label = preset.name
            if preset.hotkey:
                label += f"  ({pretty_hotkey(preset.hotkey)})"
            self.preset_combo.addItem(label)
            self.preset_combo.setItemData(
                self.preset_combo.count() - 1, preset.prompt, Qt.ItemDataRole.ToolTipRole
            )
        bar.addWidget(self.preset_combo)

        self.ask_button = QPushButton("Preguntar")
        self.ask_button.setDefault(True)
        self.ask_button.clicked.connect(lambda: self.ask(self.preset_combo.currentIndex()))
        bar.addWidget(self.ask_button)
        bar.addSeparator()

        self.custom_edit = QLineEdit()
        self.custom_edit.setPlaceholderText("Pregunta libre sobre la imagen actual… (Enter)")
        self.custom_edit.setClearButtonEnabled(True)
        self.custom_edit.setMinimumWidth(260)
        self.custom_edit.returnPressed.connect(self.ask_custom)
        bar.addWidget(self.custom_edit)
        bar.addSeparator()

        self.preview_action = QAction("Vista previa", self)
        self.preview_action.setCheckable(True)
        self.preview_action.setChecked(True)
        self.preview_action.setToolTip(
            "Ocultar la vista previa y dejar solo el panel de respuestas"
        )
        self.preview_action.toggled.connect(self.set_preview_visible)
        bar.addAction(self.preview_action)

        self.on_top_action = QAction("Siempre encima", self)
        self.on_top_action.setCheckable(True)
        self.on_top_action.toggled.connect(self.set_always_on_top)
        bar.addAction(self.on_top_action)
        self._build_menu()

    def _build_device_combo(self, devices: list[str]) -> QComboBox:
        combo = QComboBox()
        combo.setMinimumWidth(220)
        if self._config.capture.backend == "image":
            image_path = self._config.capture.image_path
            combo.addItem(Path(image_path).name if image_path else "Imagen de prueba")
            combo.setToolTip(image_path)
            combo.setEnabled(False)
        else:
            combo.addItems(devices)
            wanted = self._initial_device
            if wanted and wanted not in devices:
                combo.insertItem(0, wanted)
            index = combo.findText(wanted) if wanted else 0
            combo.setCurrentIndex(max(index, 0))
        combo.currentTextChanged.connect(self.start_source)
        return combo

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("Archivo")
        if self._history.folder is not None:
            open_folder = menu.addAction("Abrir carpeta de capturas")
            open_folder.triggered.connect(self.open_history_folder)
        if self._config.path is not None:
            edit_config = menu.addAction("Editar configuración…")
            edit_config.triggered.connect(self.open_config_file)
        self._phone_action = menu.addAction("Conectar el móvil…")
        self._phone_action.triggered.connect(self.show_phone_dialog)
        self._phone_action.setVisible(False)
        self._pair_action = menu.addAction("Emparejar el móvil sin cable…")
        self._pair_action.triggered.connect(self.show_pair_dialog)
        self._pair_action.setVisible(False)
        menu.addSeparator()
        menu.addAction("Salir", self.close)

    def _restore_window_geometry(self) -> None:
        geometry = self._settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

    # ------------------------------------------------------------------ móvil
    def _setup_phone(self, phone: PhoneServer | None) -> None:
        self._phone = phone
        self._phone_was_connected = False
        self._phone_page = 0
        self._usb_base = ""
        self._usb_status = ""
        self._adb = ""
        if phone is None:
            return
        self._phone_action.setVisible(True)
        self.panel.set_health("Móvil", None, f"abre {phone.url} en el móvil")
        self._phone_timer = QTimer(self)
        self._phone_timer.setInterval(300)
        self._phone_timer.timeout.connect(self.publish_to_phone)
        self._phone_timer.start()
        self.notify(f"Móvil: abre {phone.url} (Archivo ▸ Conectar el móvil)", 0)

    def publish_to_phone(self) -> None:
        """Copia el estado de la franja para que la página del móvil lo lea."""
        if self._phone is None:
            return
        connected = self._phone.state.connected()
        if connected:
            self._phone_was_connected = True
            self.panel.set_health("Móvil", True, "leyendo las respuestas")
            self.panel.set_alert("phone", "")
        elif connected is False and self._phone_was_connected:
            self.panel.set_health(
                "Móvil", False, "ha dejado de leer (¿pantalla apagada o sin wifi?)"
            )
            self.panel.set_alert("phone", "El móvil ha dejado de leer las respuestas.")
        cards = []
        for card in self.panel.cards[:1]:  # en el móvil solo cabe (y solo hace falta) la última
            body = html.escape(card.body.text()) if card.is_error else markdown_to_html(card.text)
            cards.append(
                {
                    "id": card.uid,
                    "title": card.title_plain,
                    "html": body,
                    "status": card.status.text(),
                    "error": card.is_error,
                    "done": card.done,
                }
            )
        self._phone.state.publish(
            {
                "cards": cards,
                "health": self.panel.health_states(),
                # El aviso de "el móvil no lee" no tiene sentido mostrarlo en el propio móvil.
                "alert": self.panel.alerts_except("phone"),
                "page": self._phone_page,
            }
        )

    def enable_usb(self, url_base: str, adb: str = "") -> None:
        """Hay adb: el móvil puede ir por cable o emparejado sin cable (http://localhost/...)."""
        self._usb_base = url_base
        self._adb = adb
        self._pair_action.setVisible(bool(adb))

    def show_pair_dialog(self) -> None:
        if self._adb:
            PairDialog(self._adb, self).exec()

    def set_usb_status(self, message: str, ok: object) -> None:
        self._usb_status = message
        if ok is not None:
            self.notify(message, 0 if ok is False else 10000)

    @property
    def phone_usb_url(self) -> str:
        if not self._usb_base or self._phone is None:
            return ""
        return f"{self._usb_base}/{self._phone.token}/"

    def show_phone_dialog(self) -> None:
        if self._phone is not None:
            PhoneDialog(
                self._phone.url, self, usb_url=self.phone_usb_url, usb_status=self._usb_status
            ).exec()

    def notify(self, message: str, timeout_ms: int = 6000) -> None:
        self.statusBar().showMessage(message, timeout_ms)

    def set_preview_visible(self, visible: bool) -> None:
        # Se colapsa con el divisor en vez de ocultar el widget para que la capturadora
        # siga entregando frames aunque no se vean.
        total = sum(self._splitter.sizes()) or self.width()
        if visible:
            self._splitter.setSizes([int(total * 0.62), int(total * 0.38)])
        else:
            self._splitter.setSizes([0, total])

    def set_always_on_top(self, on_top: bool) -> None:
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on_top)
        self.show()

    def open_history_folder(self) -> None:
        folder = self._history.folder
        if folder is None:
            return
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def open_config_file(self) -> None:
        if self._config.path is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._config.path)))
            self.notify("Reinicia CapturaIA después de guardar los cambios.", 10000)

    def enable_local_shortcuts(self) -> None:
        """Atajos dentro de la ventana, por si las teclas globales no están disponibles."""
        bindings: list[tuple[str, Callable[[], object]]] = [
            (preset.hotkey, functools.partial(self.ask, index))
            for index, preset in enumerate(self._config.presets)
        ]
        bindings.append((self._config.presenter.toggle_hotkey, self.toggle_presenter_mode))
        bindings.append((self._config.presenter.scroll_hotkey, self.panel.scroll_page))
        for hotkey, callback in bindings:
            if not hotkey:
                continue
            shortcut = QShortcut(QKeySequence(pretty_hotkey(hotkey)), self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    # ------------------------------------------------------------------ fuente
    def start_source(self, device: str) -> None:
        if self._source is not None:
            old = self._source
            old.stop()
            widget = old.preview_widget()
            self._preview_layout.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()
            old.deleteLater()
            self._source = None
        source = self._source_factory(self._config.capture, device)
        if self._config.capture.backend != "image":
            self._settings.setValue("device", device)
        source.status.connect(self._on_source_status)
        source.error.connect(self._on_source_error)
        self._preview_layout.addWidget(source.preview_widget())
        self._source = source
        self._current_device = device
        if self.presenter_mode and not self._config.presenter.show_video:
            self._set_source_preview(False)
        source.start()

    def _set_source_preview(self, enabled: bool) -> None:
        if self._source is not None:
            self._source.set_preview_enabled(enabled)
            self._source.preview_widget().setVisible(enabled)

    def _on_source_status(self, text: str) -> None:
        self._source_text = text
        self._source_label.setText(text)

    def _on_source_error(self, message: str) -> None:
        self._source_text = "Fuente con error"
        self._source_label.setText(self._source_text)
        self.notify(message, 0)

    def _refresh_stats(self) -> None:
        if self._source is None:
            return
        fps = self._source.measured_fps()
        text = self._source_text
        if fps is not None:
            text += f" · recibiendo {fps:.1f} fps"
        self._source_label.setText(text)
        self._watch_signal(fps)
        size = self._source.frame_size()
        if self.presenter_mode and size is not None and size != self._last_frame_size:
            self.apply_presenter_layout()

    def _watch_signal(self, fps: float | None) -> None:
        """Avisa si la capturadora deja de mandar imagen y la intenta reabrir."""
        if fps is None:  # imagen fija: siempre "con señal"
            self.panel.set_health("Señal", True, "imagen fija")
            return
        if fps >= MIN_LIVE_FPS:
            self._no_signal_since = None
            self.panel.set_health("Señal", True, f"{fps:.0f} fps")
            self.panel.set_alert("signal", "")
            return
        now = self._clock()
        if self._no_signal_since is None:
            self._no_signal_since = now
        if now - self._no_signal_since < NO_SIGNAL_GRACE_S:
            return
        self.panel.set_health("Señal", False, "no llega imagen de la capturadora")
        self.panel.set_alert("signal", "Sin señal de la capturadora. Reconectando…")
        if now - self._last_reconnect >= RECONNECT_EVERY_S:
            self._last_reconnect = now
            self.start_source(self._current_device)

    def has_live_signal(self) -> bool:
        fps = self._source.measured_fps() if self._source is not None else 0.0
        return fps is None or fps >= MIN_LIVE_FPS

    # ------------------------------------------------------------------ comprobaciones
    def check_gemini(self) -> None:
        """Comprueba clave y modelo al arrancar (sin gastar una pregunta)."""
        try:
            asker = self._get_asker()
        except GeminiError as exc:
            self._set_gemini_health(ok=False, detail=str(exc))
            return
        check = getattr(asker, "check", None)
        if check is None:
            self._set_gemini_health(ok=True, detail=asker.model)
            return

        def run() -> Iterator[str]:
            yield check()

        worker = AskWorker(0, run)
        worker.signals.finished.connect(
            lambda _id, name, _s: self._set_gemini_health(ok=True, detail=name)
        )
        worker.signals.failed.connect(
            lambda _id, msg: self._set_gemini_health(ok=False, detail=msg)
        )
        self._start_worker(worker)

    def _set_gemini_health(self, *, ok: bool, detail: str) -> None:
        self.panel.set_health("Gemini", ok, detail)
        self.panel.set_alert("gemini", "" if ok else f"Gemini no está listo: {detail}")

    def set_hotkeys_health(self, ok: bool, detail: str) -> None:
        self.panel.set_health("Teclas", ok, detail)
        self.panel.set_alert("hotkeys", "" if ok else f"Teclas: {detail}")

    # ------------------------------------------------------------------ modo presentación
    def handle_action(self, name: str) -> None:
        """Acciones lanzadas por teclas globales."""
        if name == "presenter":
            self.toggle_presenter_mode()
        elif name == "scroll":
            self.panel.scroll_page()
            self._phone_page += 1  # el móvil también pasa página

    def toggle_presenter_mode(self) -> None:
        self.set_presenter_mode(not self.presenter_mode)

    def set_presenter_mode(self, on: bool) -> None:
        """Imagen del PC1 a pantalla completa + franja de respuestas que nunca la tapa."""
        if on == self.presenter_mode:
            return
        cfg = self._config.presenter
        self.presenter_mode = on
        self._exit_shortcut.setEnabled(on)
        for bar in self.findChildren(QToolBar):
            bar.setVisible(not on)
        self.menuBar().setVisible(not on)
        self.statusBar().setVisible(not on)
        self.panel.set_presenter_style(on, cfg.font_size)

        if on:
            self._saved_geometry = self.saveGeometry()
            self._saved_sizes = self._splitter.sizes()
            self._splitter.setHandleWidth(0)
            if not cfg.show_video:
                # Modo atril: no se pinta la imagen; el resto de la pantalla queda en negro.
                self._set_source_preview(False)
            if cfg.side == "left":
                self._splitter.insertWidget(0, self.panel)
            self.panel.set_hint(self._presenter_hint())
            # El ratón del PC2 no pinta nada aquí: se oculta para que no tape la imagen.
            self.setCursor(Qt.CursorShape.BlankCursor)
            self._preview_box.setCursor(Qt.CursorShape.BlankCursor)
            screen = self._target_screen()
            if screen is not None:
                self.winId()  # asegura que existe la ventana nativa
                if self.windowHandle() is not None:
                    self.windowHandle().setScreen(screen)
                self.setGeometry(screen.geometry())
            self.showFullScreen()
            self.apply_presenter_layout()
            QTimer.singleShot(0, self.apply_presenter_layout)
        else:
            self._splitter.setHandleWidth(self._handle_width)
            self._splitter.insertWidget(0, self._preview_box)
            self._set_source_preview(True)
            self.panel.set_hint(self._normal_hint)
            self.unsetCursor()
            self._preview_box.unsetCursor()
            self.showNormal()
            if self._saved_geometry is not None:
                self.restoreGeometry(self._saved_geometry)
            if self._saved_sizes:
                self._splitter.setSizes(self._saved_sizes)
            self.preview_action.setChecked(True)

    def _target_screen(self) -> Any:
        screens = QGuiApplication.screens()
        number = self._config.presenter.screen
        if 1 <= number <= len(screens):
            return screens[number - 1]
        return self.screen()

    def _presenter_hint(self) -> str:
        cfg = self._config.presenter
        keys = " / ".join(
            f"{pretty_hotkey(p.hotkey)} {p.name}" for p in self._config.presets if p.hotkey
        )
        extra = []
        if cfg.scroll_hotkey:
            extra.append(f"{pretty_hotkey(cfg.scroll_hotkey)}: pasar página")
        extra.append(f"{pretty_hotkey(cfg.toggle_hotkey) or 'Esc'}: salir")
        return f"{keys}\n\n" + " · ".join(extra)

    def apply_presenter_layout(self) -> None:
        if not self.presenter_mode:
            return
        cfg = self._config.presenter
        area = self._splitter.size()
        frame = self._source.frame_size() if self._source is not None else None
        self._last_frame_size = frame
        if cfg.show_video:
            frame_w = frame.width() if frame else self._config.capture.width
            frame_h = frame.height() if frame else self._config.capture.height
            video_w, strip_w = presenter_split(
                area.width(), area.height(), frame_w, frame_h, cfg.strip_width
            )
        else:
            strip_w = min(cfg.strip_width, area.width())
            video_w = area.width() - strip_w
        if cfg.side == "left":
            self._splitter.setSizes([strip_w, video_w])
        else:
            self._splitter.setSizes([video_w, strip_w])

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.presenter_mode:
            QTimer.singleShot(0, self.apply_presenter_layout)

    # ------------------------------------------------------------------ preguntas
    def ask(self, preset_index: int) -> int | None:
        if not 0 <= preset_index < len(self._config.presets):
            return None
        preset = self._config.presets[preset_index]
        return self._ask(preset_index, preset.name, preset.prompt)

    def ask_custom(self) -> int | None:
        prompt = self.custom_edit.text().strip()
        if not prompt:
            return None
        self.custom_edit.clear()
        return self._ask(None, "Pregunta libre", prompt)

    def _ask(self, busy_key: int | None, title: str, prompt: str) -> int | None:
        if busy_key is not None and busy_key in self._busy:
            self.notify(f"«{title}» ya está en curso; espera a que termine.")
            return None
        frame = self._source.grab_frame() if self._source is not None else None
        if frame is None or not self.has_live_signal():
            message = "Sin señal de la capturadora: no he enviado nada a Gemini."
            self.notify(message)
            if self.presenter_mode:  # la barra de estado no se ve: aviso en la franja
                self.panel.add_card(title, prompt, QImage(), datetime.now()).mark_error(message)
            return None
        capture = self._config.capture
        try:
            jpeg = qimage_to_jpeg(frame, capture.jpeg_quality, capture.max_width)
        except (ValueError, RuntimeError) as exc:
            self.notify(str(exc))
            return None

        when = datetime.now()
        card = self.panel.add_card(title, prompt, frame, when)
        try:
            asker = self._get_asker()
        except GeminiError as exc:
            card.mark_error(str(exc))
            return None

        request_id = self._next_id
        self._next_id += 1
        self._requests[request_id] = _Request(
            card=card,
            busy_key=busy_key,
            title=title,
            prompt=prompt,
            jpeg=jpeg,
            when=when,
            model=asker.model,
        )
        if busy_key is not None:
            self._busy[busy_key] = request_id

        worker = AskWorker(request_id, functools.partial(asker.ask_stream, jpeg, prompt))
        worker.signals.chunk.connect(self._on_chunk)
        worker.signals.finished.connect(self._on_finished)
        worker.signals.failed.connect(self._on_failed)
        self._start_worker(worker)
        return request_id

    def _start_worker(self, worker: AskWorker) -> None:
        """Lanza la petición y mantiene vivo el worker (y sus señales) hasta que termina.

        Si nadie guarda una referencia, Python puede liberar el objeto de señales mientras la
        petición sigue en marcha: la respuesta se pierde o la app se cae.
        """
        worker.setAutoDelete(False)
        key = self._next_worker_key
        self._next_worker_key += 1
        self._workers[key] = worker

        def release(*_args: object) -> None:
            # Diferido: no se puede destruir el emisor mientras entrega su propia señal.
            QTimer.singleShot(0, lambda: self._workers.pop(key, None))

        worker.signals.finished.connect(release)
        worker.signals.failed.connect(release)
        self._pool.start(worker)

    def _get_asker(self) -> Asker:
        if self._asker is None:
            self._asker = self._asker_factory()
        return self._asker

    def _release(self, request_id: int) -> _Request | None:
        request = self._requests.pop(request_id, None)
        if request is not None and request.busy_key is not None:
            self._busy.pop(request.busy_key, None)
        return request

    def _on_chunk(self, request_id: int, text: str) -> None:
        request = self._requests.get(request_id)
        if request is not None:
            request.card.append_text(text)

    def _on_finished(self, request_id: int, text: str, seconds: float) -> None:
        request = self._release(request_id)
        if request is None:
            return
        saved = None
        try:
            saved = self._history.save(
                when=request.when,
                preset=request.title,
                prompt=request.prompt,
                jpeg=request.jpeg,
                answer=text,
                model=request.model,
            )
        except OSError as exc:
            self.notify(f"No se pudo guardar en el historial: {exc}")
        request.card.mark_done(seconds, saved)
        self._set_gemini_health(ok=True, detail=request.model)

    def _on_failed(self, request_id: int, message: str) -> None:
        request = self._release(request_id)
        if request is not None:
            request.card.mark_error(message)
            self.panel.set_health("Gemini", False, message)

    @property
    def pending_requests(self) -> int:
        return len(self._requests)

    def closeEvent(self, event: QCloseEvent) -> None:
        geometry = self._saved_geometry if self.presenter_mode else self.saveGeometry()
        if geometry is not None:
            self._settings.setValue("geometry", geometry)
        if self._source is not None:
            self._source.stop()
        super().closeEvent(event)
