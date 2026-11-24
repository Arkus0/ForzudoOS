"""Controlador: pantalla de inicio ⇄ app, con el móvil, el cable/adb y las teclas compartidos."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QSettings, QTimer

from capturaia.config import AppConfig, GeminiConfig, Preset
from capturaia.gemini import Asker
from capturaia.hotkeys import HotkeyBridge, pretty_hotkey
from capturaia.phone import PhoneServer, PhoneState
from capturaia.ui.main_window import MainWindow
from capturaia.ui.setup_window import SetupWindow
from capturaia.usb_bridge import UsbBridge, find_adb

AskerFactory = Callable[[GeminiConfig], Asker]


def start_phone(config: AppConfig, settings: QSettings | None = None) -> PhoneServer | None:
    """Arranca la página del móvil; la clave de la dirección se guarda para que no cambie."""
    if not config.phone.enabled:
        return None
    settings = settings or QSettings("CapturaIA", "CapturaIA")
    token = str(settings.value("phone_token", "") or "")
    if not token:
        token = secrets.token_urlsafe(9)
        settings.setValue("phone_token", token)
    server = PhoneServer(PhoneState(), token, config.phone.port, config.phone.font_size)
    try:
        server.start()
    except OSError:
        return None
    return server


class CapturaApp(QObject):
    def __init__(
        self,
        config: AppConfig,
        *,
        presenter: bool = False,
        asker_factory: AskerFactory | None = None,
        phone: PhoneServer | bool | None = True,
        keyboard_module: Any = None,
        window_kwargs: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self.config = config
        self._presenter = presenter
        self._asker_factory = asker_factory
        self._keyboard = keyboard_module
        self._window_kwargs = window_kwargs or {}
        if phone is True:
            self.phone = start_phone(config)
        else:
            self.phone = phone or None
        self.phone_failed = config.phone.enabled and self.phone is None
        self.usb: UsbBridge | None = None
        self.adb = ""
        self.usb_status: tuple[str, bool | None] = ("", None)
        self.hotkeys: HotkeyBridge | None = None
        self.setup: SetupWindow | None = None
        self.main: MainWindow | None = None
        self._keys_timer = QTimer(self)
        self._keys_timer.setSingleShot(True)
        self._keys_timer.setInterval(200)
        self._keys_timer.timeout.connect(self._setup_keys_changed)
        self.start_usb()

    # ------------------------------------------------------------------ cable / adb
    @property
    def usb_base(self) -> str:
        return self.usb.url_base if self.usb is not None else ""

    def start_usb(self) -> None:
        if self.usb is not None or self.phone is None or not self.config.phone.usb:
            return
        adb = find_adb(self.config.phone.adb_path)
        if adb is None:
            return
        self.adb = adb
        self.usb = UsbBridge(adb, self.config.phone.port)
        self.usb.status.connect(self._on_usb_status)
        self.usb.start()
        if self.setup is not None:
            self.setup.set_usb(self.adb, self.usb_base)

    def _on_usb_status(self, message: str, ok: object) -> None:
        self.usb_status = (message, ok)  # type: ignore[assignment]
        if self.setup is not None:
            self.setup.set_usb_status(message, ok)
        if self.main is not None:
            self.main.set_usb_status(message, ok)

    # ------------------------------------------------------------------ teclas globales
    def _restart_hotkeys(self, presets: list[Preset], actions: dict[str, str]) -> tuple[bool, str]:
        if self.hotkeys is not None:
            self.hotkeys.stop()
        self.hotkeys = HotkeyBridge(presets, actions=actions, keyboard_module=self._keyboard)
        self.hotkeys.triggered.connect(self._on_preset_key)
        self.hotkeys.action.connect(self._on_action_key)
        warnings = self.hotkeys.start()
        active = ", ".join(pretty_hotkey(k) for k in self.hotkeys.active)
        ok = bool(self.hotkeys.active) and not warnings
        return ok, " · ".join(warnings) or f"activas: {active}"

    def _on_preset_key(self, index: int) -> None:
        if self.main is not None:
            self.main.ask(index)
        elif self.setup is not None:
            self.setup.mark_preset_received(index)

    def _on_action_key(self, name: str) -> None:
        if self.main is not None:
            self.main.handle_action(name)
        elif self.setup is not None:
            self.setup.mark_action_received(name)

    def _setup_keys_changed(self) -> None:
        if self.setup is None:
            return
        try:
            ok, detail = self._restart_hotkeys(
                self.setup.presets_for_hotkeys(), self.setup.actions_for_hotkeys()
            )
        except ValueError as exc:
            ok, detail = False, str(exc)
        self.setup.set_hotkeys_status(ok, detail)

    # ------------------------------------------------------------------ ventanas
    def show_setup(self, *, auto_start: bool = True) -> SetupWindow:
        factory = self._asker_factory
        setup = SetupWindow(
            self.config, phone=self.phone, asker_factory=factory, auto_start=auto_start
        )
        setup.set_usb(self.adb, self.usb_base)
        setup.set_usb_status(*self.usb_status)
        setup.start_requested.connect(self.start_main)
        setup.keys_changed.connect(self._keys_timer.start)
        setup.adb_search_requested.connect(self.start_usb)
        self.setup = setup
        setup.show()
        if self.main is not None:  # se muestra la nueva antes de cerrar la vieja
            old, self.main = self.main, None
            old.close()
            old.deleteLater()
        self._setup_keys_changed()
        return setup

    def start_main(self, config: AppConfig) -> MainWindow:
        self.config = config
        factory = self._asker_factory
        window = MainWindow(
            config,
            phone=self.phone,
            asker_factory=(lambda: factory(config.gemini)) if factory else None,
            **self._window_kwargs,
        )
        if self.adb:
            window.enable_usb(self.usb_base, self.adb)
            window.set_usb_status(*self.usb_status)
        if self.phone_failed:
            window.notify(
                f"No se pudo abrir la página del móvil en el puerto {config.phone.port} "
                "(¿otro programa lo usa? Cámbialo en [phone] port).",
                0,
            )
        window.setup_requested.connect(lambda: self.show_setup(auto_start=False))
        self.main = window
        presenter = config.presenter
        ok, detail = self._restart_hotkeys(
            list(config.presets),
            {"presenter": presenter.toggle_hotkey, "scroll": presenter.scroll_hotkey},
        )
        window.set_hotkeys_health(ok, detail)
        if self.hotkeys is not None and not self.hotkeys.active:
            window.enable_local_shortcuts()
        window.show()
        if self._presenter or presenter.start:
            window.set_presenter_mode(True)
        if self.setup is not None:
            old, self.setup = self.setup, None
            old.close()
            old.deleteLater()
        return window

    def shutdown(self) -> None:
        if self.hotkeys is not None:
            self.hotkeys.stop()
        if self.usb is not None:
            self.usb.stop()
        if self.phone is not None:
            self.phone.stop()
