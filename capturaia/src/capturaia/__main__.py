"""Punto de entrada: `uv run capturaia` o `python -m capturaia`."""

from __future__ import annotations

import argparse
import secrets
import sys
import threading
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from capturaia import __version__
from capturaia.config import AppConfig, ConfigError, default_config_path, load_config

if TYPE_CHECKING:
    from capturaia.phone import PhoneServer
    from capturaia.ui.main_window import MainWindow
    from capturaia.usb_bridge import UsbBridge


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="capturaia",
        description=(
            "Captura el frame de la capturadora, se lo pregunta a Gemini y muestra la respuesta."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        help=f"archivo de configuración (por defecto {default_config_path()})",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="muestra las capturadoras/cámaras detectadas y sale",
    )
    parser.add_argument(
        "--demo",
        nargs="?",
        const="",
        metavar="IMAGEN",
        help="usa una imagen fija en lugar de la capturadora (sin IMAGEN: imagen de prueba)",
    )
    parser.add_argument(
        "--presentar",
        action="store_true",
        help="arranca en modo presentación (imagen a pantalla completa + franja de respuestas)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: PLC0415

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("CapturaIA")
    app.setOrganizationName("CapturaIA")

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        QMessageBox.critical(None, "CapturaIA: configuración", str(exc))
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return 1

    if args.list_devices:
        from capturaia.capture.qt_source import list_devices  # noqa: PLC0415

        devices = list_devices()
        print("\n".join(devices) if devices else "No se ha detectado ningún dispositivo de vídeo.")
        return 0

    if args.demo is not None:
        config = replace(
            config, capture=replace(config.capture, backend="image", image_path=args.demo)
        )

    # Precarga el SDK de Gemini en segundo plano para que la primera pregunta no espere.
    threading.Thread(target=__import__, args=("google.genai",), daemon=True).start()

    from capturaia.hotkeys import HotkeyBridge, pretty_hotkey  # noqa: PLC0415
    from capturaia.ui.main_window import MainWindow  # noqa: PLC0415

    phone = _start_phone(config)
    window = MainWindow(config, phone=phone)
    usb = _start_usb(config, window) if phone is not None else None
    if config.phone.enabled and phone is None:
        window.notify(
            f"No se pudo abrir la página del móvil en el puerto {config.phone.port} "
            "(¿otro programa lo usa? Cámbialo en [phone] port).",
            0,
        )
    presenter = config.presenter
    hotkeys = HotkeyBridge(
        config.presets,
        actions={"presenter": presenter.toggle_hotkey, "scroll": presenter.scroll_hotkey},
    )
    hotkeys.triggered.connect(window.ask)
    hotkeys.action.connect(window.handle_action)
    warnings = hotkeys.start()
    if warnings:
        window.notify(" · ".join(warnings), 0)
    active = ", ".join(pretty_hotkey(k) for k in hotkeys.active)
    window.set_hotkeys_health(
        bool(hotkeys.active) and not warnings, " · ".join(warnings) or f"activas: {active}"
    )
    if not hotkeys.active:
        window.enable_local_shortcuts()
    if config.path is not None:
        print(f"Configuración: {config.path}")

    window.show()
    if args.presentar or presenter.start:
        window.set_presenter_mode(True)
    try:
        return app.exec()
    finally:
        hotkeys.stop()
        if usb is not None:
            usb.stop()
        if phone is not None:
            phone.stop()


def _start_usb(config: AppConfig, window: MainWindow) -> UsbBridge | None:
    """Si hay adb, mantiene el móvil accesible por cable como http://localhost."""
    if not config.phone.usb:
        return None
    from capturaia.usb_bridge import UsbBridge, find_adb  # noqa: PLC0415

    adb = find_adb(config.phone.adb_path)
    if adb is None:
        return None
    bridge = UsbBridge(adb, config.phone.port)
    bridge.status.connect(window.set_usb_status)
    window.enable_usb(bridge.url_base, adb)
    bridge.start()
    return bridge


def _start_phone(config: AppConfig) -> PhoneServer | None:
    """Arranca la página del móvil; la clave de la dirección se guarda para que no cambie."""
    if not config.phone.enabled:
        return None
    from PySide6.QtCore import QSettings  # noqa: PLC0415

    from capturaia.phone import PhoneServer, PhoneState  # noqa: PLC0415

    settings = QSettings("CapturaIA", "CapturaIA")
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


if __name__ == "__main__":
    raise SystemExit(main())
