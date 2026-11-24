"""Ventana con la dirección y el código QR para abrir las respuestas en el móvil."""

from __future__ import annotations

import io

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget

INSTRUCTIONS = (
    "<b>1.</b> Conecta el móvil a la misma wifi que este PC.<br>"
    "<b>2.</b> Escanea el código con la cámara del móvil (o escribe la dirección).<br>"
    "<b>3.</b> Para que no se apague la pantalla: deja el móvil cargando y activa "
    "«Pantalla activa» en Opciones para desarrolladores (Android) o pon el Bloqueo "
    "automático en «Nunca» (iPhone).<br>"
    "<b>4.</b> Baja el brillo del móvil: el fondo es negro y el texto se lee igual. "
    "Desde la propia página puedes cambiar el tamaño de letra (A−/A+) y el brillo del texto "
    "(☀−/☀+).<br><br>"
    "La primera vez, Windows puede preguntar si permite el acceso de red a Python: "
    "acepta solo para <b>redes privadas</b>."
)


def qr_pixmap(text: str, scale: int = 8) -> QPixmap:
    import segno  # noqa: PLC0415

    buffer = io.BytesIO()
    segno.make(text, error="m").save(buffer, kind="png", scale=scale, border=2)
    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue(), "PNG")
    return pixmap


class PhoneDialog(QDialog):
    def __init__(self, url: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Conectar el móvil")
        layout = QVBoxLayout(self)

        self.qr = QLabel()
        self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        try:
            self.qr.setPixmap(qr_pixmap(url))
        except Exception:  # sin segno el QR no es imprescindible: queda la dirección
            self.qr.setText("(no se pudo generar el código QR)")
        layout.addWidget(self.qr)

        self.url = QLabel(f'<a href="{url}" style="font-size:16pt">{url}</a>')
        self.url.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.url.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.url.setOpenExternalLinks(True)
        layout.addWidget(self.url)

        help_text = QLabel(INSTRUCTIONS)
        help_text.setWordWrap(True)
        help_text.setMaximumWidth(520)
        layout.addWidget(help_text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
