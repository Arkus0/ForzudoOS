"""Panel lateral con las respuestas de Gemini (la más reciente arriba)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

CARD_STYLE = """
QFrame#card {
    background: palette(base);
    border: 1px solid palette(mid);
    border-radius: 8px;
}
QLabel#meta, QLabel#prompt, QLabel#status { color: palette(placeholder-text); }
"""

# Modo presentación: fondo oscuro y alto contraste para leer de un vistazo.
PRESENTER_BG = "#101114"
PRESENTER_CARD_STYLE = """
QFrame#card { background: #1b1d22; border: 1px solid #2c2f36; border-radius: 10px; }
QFrame#card[latest="true"] { border: 2px solid #4da3ff; }
QLabel { color: #f2f2f2; }
QLabel#title { color: #8cc4ff; }
QLabel#meta, QLabel#status { color: #9aa0a6; }
"""
ERROR_COLOR = "#ff6b6b"


class AnswerCard(QFrame):
    def __init__(self, title: str, prompt: str, image: QImage, when: datetime) -> None:
        super().__init__()
        self.setObjectName("card")
        self.setStyleSheet(CARD_STYLE)
        self._text = ""
        self.done = False
        self._error = False
        self._compact = False
        self._done_info: tuple[float, Path | None] | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        self.title = QLabel(f"<b>{_escape(title)}</b>")
        self.title.setObjectName("title")
        self.title.setWordWrap(True)
        self.meta = QLabel(when.strftime("%H:%M:%S"))
        self.meta.setObjectName("meta")
        self._copy = QToolButton()
        self._copy.setText("Copiar")
        self._copy.setToolTip("Copiar la respuesta al portapapeles")
        self._copy.setEnabled(False)
        self._copy.clicked.connect(self.copy_to_clipboard)
        header.addWidget(self.title)
        header.addStretch(1)
        header.addWidget(self.meta)
        header.addWidget(self._copy)
        layout.addLayout(header)

        self.thumbnail = QLabel()
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignLeft)
        if not image.isNull():
            self.thumbnail.setPixmap(
                QPixmap.fromImage(
                    image.scaledToWidth(240, Qt.TransformationMode.SmoothTransformation)
                )
            )
        layout.addWidget(self.thumbnail)

        self.prompt = QLabel(prompt)
        self.prompt.setObjectName("prompt")
        self.prompt.setWordWrap(True)
        layout.addWidget(self.prompt)

        self.body = QLabel()
        self.body.setTextFormat(Qt.TextFormat.MarkdownText)
        self.body.setWordWrap(True)
        self.body.setOpenExternalLinks(True)
        self.body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self.body.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.body.hide()
        layout.addWidget(self.body)

        self.status = QLabel("Pensando…")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)  # si no, una línea larga ensancha la tarjeta y la corta
        layout.addWidget(self.status)

    @property
    def text(self) -> str:
        return self._text

    def append_text(self, chunk: str) -> None:
        self._text += chunk
        self.body.setText(self._text)
        self.body.show()
        self.status.setText("Escribiendo…")

    def mark_done(self, seconds: float, saved: Path | None = None) -> None:
        self.done = True
        self._copy.setEnabled(True)
        self._done_info = (seconds, saved)
        self._refresh_done_status()

    def _refresh_done_status(self) -> None:
        if self._done_info is None or self._error:
            return
        seconds, saved = self._done_info
        extra = f" · guardado en {saved.name}" if saved and not self._compact else ""
        self.status.setText(f"Listo en {seconds:.1f} s{extra}")

    def mark_error(self, message: str) -> None:
        self.done = True
        self._error = True
        self.body.setTextFormat(Qt.TextFormat.PlainText)
        self.body.setStyleSheet(f"color: {ERROR_COLOR};")
        self.body.setText(message)
        self.body.show()
        self.status.setText("Error")

    def set_presenter_style(self, on: bool, font_pt: int) -> None:
        """Letra grande y sin miniatura ni pregunta: solo lo que hay que leer."""
        self._compact = on
        self.setStyleSheet(PRESENTER_CARD_STYLE if on else CARD_STYLE)
        self._refresh_done_status()
        self.thumbnail.setVisible(not on)
        self.prompt.setVisible(not on)
        self._copy.setVisible(not on)
        self.meta.setVisible(not on)
        for label, scale in ((self.body, 1.0), (self.title, 0.75), (self.status, 0.6)):
            font = self.font()
            if on:
                font.setPointSizeF(font_pt * scale)
            label.setFont(font)

    def set_latest(self, latest: bool) -> None:
        if self.property("latest") != latest:
            self.setProperty("latest", latest)
            self.style().unpolish(self)
            self.style().polish(self)

    def copy_to_clipboard(self) -> None:
        QGuiApplication.clipboard().setText(self._text)


class AnswerPanel(QWidget):
    def __init__(self, hint: str, max_cards: int = 30) -> None:
        super().__init__()
        self._max_cards = max_cards
        self.cards: list[AnswerCard] = []
        self.presenter = False
        self._font_pt = 20

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._header = QWidget()
        header = QHBoxLayout(self._header)
        header.setContentsMargins(8, 6, 8, 0)
        header.addWidget(QLabel("<b>Respuestas</b>"))
        header.addStretch(1)
        clear = QPushButton("Limpiar")
        clear.clicked.connect(self.clear)
        header.addWidget(clear)
        layout.addWidget(self._header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        self._list = QVBoxLayout(container)
        self._list.setContentsMargins(8, 8, 8, 8)
        self._list.setSpacing(8)
        self._empty = QLabel(hint)
        self._empty.setWordWrap(True)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setObjectName("status")
        self._list.addWidget(self._empty)
        self._list.addStretch(1)
        self._scroll.setWidget(container)
        layout.addWidget(self._scroll)
        self._apply_panel_style()

    def set_hint(self, hint: str) -> None:
        self._empty.setText(hint)

    def set_presenter_style(self, on: bool, font_pt: int = 20) -> None:
        self.presenter = on
        self._font_pt = font_pt
        self._header.setVisible(not on)
        self._apply_panel_style()
        for card in self.cards:
            card.set_presenter_style(on, font_pt)

    def _apply_panel_style(self) -> None:
        if self.presenter:
            self.setStyleSheet(
                f"AnswerPanel, QScrollArea, QScrollArea > QWidget > QWidget "
                f"{{ background: {PRESENTER_BG}; }}"
            )
            self._empty.setStyleSheet(
                f"color: #9aa0a6; padding: 24px; font-size: {max(12, self._font_pt - 6)}pt;"
            )
        else:
            self.setStyleSheet("")
            self._empty.setStyleSheet("color: palette(placeholder-text); padding: 24px;")

    def scroll_page(self) -> int:
        """Baja una página; si ya está abajo del todo, vuelve arriba. Devuelve la posición."""
        bar = self._scroll.verticalScrollBar()
        if bar.value() >= bar.maximum():
            bar.setValue(bar.minimum())
        else:
            bar.setValue(min(bar.value() + max(bar.pageStep() - 40, 40), bar.maximum()))
        return bar.value()

    def add_card(self, title: str, prompt: str, image: QImage, when: datetime) -> AnswerCard:
        self._empty.hide()
        card = AnswerCard(title, prompt, image, when)
        if self.presenter:
            card.set_presenter_style(True, self._font_pt)
        for old in self.cards:
            old.set_latest(False)
        card.set_latest(True)
        self._list.insertWidget(0, card)
        self.cards.insert(0, card)
        self._trim()
        self._scroll.verticalScrollBar().setValue(0)
        return card

    def _trim(self) -> None:
        # Quita las tarjetas antiguas ya terminadas para no acumular memoria.
        while len(self.cards) > self._max_cards:
            old = next((c for c in reversed(self.cards) if c.done), None)
            if old is None:
                break
            self.cards.remove(old)
            old.setParent(None)
            old.deleteLater()

    def clear(self) -> None:
        for card in [c for c in self.cards if c.done]:
            self.cards.remove(card)
            card.setParent(None)
            card.deleteLater()
        if not self.cards:
            self._empty.show()


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
