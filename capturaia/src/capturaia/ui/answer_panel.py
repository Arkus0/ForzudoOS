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


class AnswerCard(QFrame):
    def __init__(self, title: str, prompt: str, image: QImage, when: datetime) -> None:
        super().__init__()
        self.setObjectName("card")
        self.setStyleSheet(CARD_STYLE)
        self._text = ""
        self.done = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title_label = QLabel(f"<b>{_escape(title)}</b>")
        meta = QLabel(when.strftime("%H:%M:%S"))
        meta.setObjectName("meta")
        self._copy = QToolButton()
        self._copy.setText("Copiar")
        self._copy.setToolTip("Copiar la respuesta al portapapeles")
        self._copy.setEnabled(False)
        self._copy.clicked.connect(self.copy_to_clipboard)
        header.addWidget(title_label)
        header.addStretch(1)
        header.addWidget(meta)
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

        prompt_label = QLabel(prompt)
        prompt_label.setObjectName("prompt")
        prompt_label.setWordWrap(True)
        layout.addWidget(prompt_label)

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
        extra = f" · guardado en {saved.name}" if saved else ""
        self.status.setText(f"Listo en {seconds:.1f} s{extra}")

    def mark_error(self, message: str) -> None:
        self.done = True
        self.body.setTextFormat(Qt.TextFormat.PlainText)
        self.body.setStyleSheet("color: #d9534f;")
        self.body.setText(message)
        self.body.show()
        self.status.setText("Error")

    def copy_to_clipboard(self) -> None:
        QGuiApplication.clipboard().setText(self._text)


class AnswerPanel(QWidget):
    def __init__(self, hint: str, max_cards: int = 30) -> None:
        super().__init__()
        self._max_cards = max_cards
        self.cards: list[AnswerCard] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        header.setContentsMargins(8, 6, 8, 0)
        header.addWidget(QLabel("<b>Respuestas</b>"))
        header.addStretch(1)
        clear = QPushButton("Limpiar")
        clear.clicked.connect(self.clear)
        header.addWidget(clear)
        layout.addLayout(header)

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
        self._empty.setStyleSheet("color: palette(placeholder-text); padding: 24px;")
        self._list.addWidget(self._empty)
        self._list.addStretch(1)
        self._scroll.setWidget(container)
        layout.addWidget(self._scroll)

    def add_card(self, title: str, prompt: str, image: QImage, when: datetime) -> AnswerCard:
        self._empty.hide()
        card = AnswerCard(title, prompt, image, when)
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
