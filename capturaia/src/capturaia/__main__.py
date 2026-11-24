"""Punto de entrada: `uv run capturaia` o `python -m capturaia`."""

from __future__ import annotations

import argparse
import sys
import threading
from dataclasses import replace
from pathlib import Path

from capturaia import __version__
from capturaia.config import ConfigError, default_config_path, load_config


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

    from capturaia.hotkeys import HotkeyBridge  # noqa: PLC0415
    from capturaia.ui.main_window import MainWindow  # noqa: PLC0415

    window = MainWindow(config)
    hotkeys = HotkeyBridge(config.presets)
    hotkeys.triggered.connect(window.ask)
    warnings = hotkeys.start()
    if warnings:
        window.notify(" · ".join(warnings), 0)
    if not hotkeys.active:
        window.enable_local_shortcuts()
    if config.path is not None:
        print(f"Configuración: {config.path}")

    window.show()
    try:
        return app.exec()
    finally:
        hotkeys.stop()


if __name__ == "__main__":
    raise SystemExit(main())
