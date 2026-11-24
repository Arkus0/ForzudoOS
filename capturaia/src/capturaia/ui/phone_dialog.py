"""Ventana con la dirección y el código QR para abrir las respuestas en el móvil."""

from __future__ import annotations

import io
from collections.abc import Callable, Sequence
from urllib.parse import urlsplit

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

COMMON_TIPS = (
    "Pon el móvil en horizontal y toca la pantalla una vez: pasa a pantalla completa. Cada "
    "toque muestra unos segundos los controles de letra (A−/A+) y brillo (☀−/☀+). Baja también "
    "el brillo del móvil: el fondo es negro."
)


def usb_instructions(status: str) -> str:
    return (
        "<b>Por cable USB o emparejado sin cable (recomendado)</b>: la dirección no cambia "
        "nunca (Archivo ▸ Emparejar el móvil sin cable para la opción sin cable).<br>"
        "<b>1.</b> Una sola vez: activa «Depuración USB» en Opciones para desarrolladores del "
        "móvil y acepta el aviso «¿Permitir depuración USB?» al conectarlo (marca «Permitir "
        "siempre»).<br>"
        "<b>2.</b> Con el cable puesto, escanea el código o escribe la dirección. Añádela a la "
        "pantalla de inicio (Chrome ▸ ⋮ ▸ Añadir a pantalla de inicio).<br>"
        "<b>3.</b> La pantalla no se apagará: la página la bloquea encendida («Pantalla fija») "
        "y el cable carga el móvil.<br>"
        f"<b>4.</b> {COMMON_TIPS}<br><br>"
        f"Estado: <b>{status or 'comprobando…'}</b>"
    )


def wifi_instructions(origin: str) -> str:
    return (
        "<b>Por wifi</b>:<br>"
        "<b>1.</b> Conecta el móvil a la misma wifi que este PC.<br>"
        "<b>2.</b> Escanea el código con la cámara del móvil (o escribe la dirección).<br>"
        "<b>3.</b> Para que no se apague la pantalla (Chrome en Android): abre "
        "<code>chrome://flags</code>, busca <i>Insecure origins treated as secure</i>, escribe "
        f"<code>{origin}</code>, ponlo en <i>Enabled</i> y pulsa <i>Relaunch</i>. Si el router "
        "cambia la IP de este PC, hay que repetirlo.<br>"
        f"<b>4.</b> {COMMON_TIPS}<br><br>"
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
    """Muestra la dirección por cable USB (si hay adb) y la de wifi, con QR de la primera."""

    def __init__(
        self,
        wifi_url: str,
        parent: QWidget | None = None,
        *,
        usb_url: str = "",
        usb_status: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Conectar el móvil")
        layout = QVBoxLayout(self)
        main_url = usb_url or wifi_url

        self.qr = QLabel()
        self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        try:
            self.qr.setPixmap(qr_pixmap(main_url))
        except Exception:  # sin segno el QR no es imprescindible: queda la dirección
            self.qr.setText("(no se pudo generar el código QR)")
        layout.addWidget(self.qr)

        self.url = _link(main_url)
        layout.addWidget(self.url)

        if usb_url:
            layout.addWidget(_text(usb_instructions(usb_status)))
            layout.addWidget(_text("<hr>Alternativa:"))
            layout.addWidget(_link(wifi_url, size=11))
        parts = urlsplit(wifi_url)
        layout.addWidget(_text(wifi_instructions(f"{parts.scheme}://{parts.netloc}")))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


def _link(url: str, size: int = 16) -> QLabel:
    label = QLabel(f'<a href="{url}" style="font-size:{size}pt">{url}</a>')
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
    label.setOpenExternalLinks(True)
    return label


def _text(content: str) -> QLabel:
    label = QLabel(content)
    label.setWordWrap(True)
    label.setMaximumWidth(560)
    return label


PAIR_HELP = (
    "<b>Emparejar el móvil sin cable</b> (una sola vez; el móvil y este PC en la misma wifi):<br>"
    "<b>1.</b> En el móvil: Ajustes ▸ Sistema ▸ Opciones para desarrolladores ▸ "
    "<b>Depuración inalámbrica</b> ▸ actívala.<br>"
    "<b>2.</b> Toca «Vincular dispositivo con código de vinculación». Aparecen una dirección "
    "(IP:puerto) y un código de 6 cifras.<br>"
    "<b>3.</b> Escríbelos aquí y pulsa «Emparejar».<br><br>"
    "Después no hay que repetirlo: cuando el móvil tenga activada la Depuración inalámbrica y "
    "esté en tu wifi, CapturaIA lo conecta sola y la página se abre como "
    "<code>http://localhost</code> (sin IP fija y con la pantalla fija). Si Android la desactiva "
    "(por ejemplo, al cambiar de wifi o al reiniciar), vuelve a activar el interruptor; no hace "
    "falta volver a emparejar."
)


class PairDialog(QDialog):
    """Empareja el móvil por depuración inalámbrica con `adb pair`."""

    def __init__(
        self,
        adb: str,
        parent: QWidget | None = None,
        *,
        runner: Callable[[Sequence[str]], str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Emparejar el móvil sin cable")
        self._adb = adb
        self._runner = runner
        layout = QVBoxLayout(self)
        layout.addWidget(_text(PAIR_HELP))

        form = QFormLayout()
        self.address = QLineEdit()
        self.address.setPlaceholderText("192.168.1.30:37123")
        self.code = QLineEdit()
        self.code.setPlaceholderText("123456")
        self.code.setMaxLength(6)
        form.addRow("IP:puerto", self.address)
        form.addRow("Código", self.code)
        layout.addLayout(form)

        self.pair_button = QPushButton("Emparejar")
        self.pair_button.clicked.connect(self.do_pair)
        layout.addWidget(self.pair_button)
        self.result = _text("")
        layout.addWidget(self.result)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def do_pair(self) -> bool:
        from capturaia.usb_bridge import pair  # noqa: PLC0415

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            if self._runner is None:
                ok, message = pair(self._adb, self.address.text(), self.code.text())
            else:
                ok, message = pair(self._adb, self.address.text(), self.code.text(), self._runner)
        finally:
            QApplication.restoreOverrideCursor()
        color = "#3fb950" if ok else "#d9534f"
        self.result.setText(f'<span style="color:{color}">{message}</span>')
        return ok
