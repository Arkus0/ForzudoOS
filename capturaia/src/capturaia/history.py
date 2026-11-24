"""Guarda en disco cada captura con su pregunta y respuesta."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


class History:
    def __init__(self, folder: Path | None, *, enabled: bool = True) -> None:
        self.folder = folder
        self.enabled = enabled and folder is not None

    def save(
        self,
        *,
        when: datetime,
        preset: str,
        prompt: str,
        jpeg: bytes,
        answer: str,
        model: str,
    ) -> Path | None:
        """Escribe AAAA-MM-DD_HHMMSS.jpg y .md; devuelve la ruta del .md (None si está apagado)."""
        if not self.enabled or self.folder is None:
            return None
        self.folder.mkdir(parents=True, exist_ok=True)
        stem = self._free_stem(when.strftime("%Y-%m-%d_%H%M%S"))
        image_path = self.folder / f"{stem}.jpg"
        note_path = self.folder / f"{stem}.md"
        image_path.write_bytes(jpeg)
        note_path.write_text(
            f"# {preset}\n\n"
            f"- Fecha: {when:%Y-%m-%d %H:%M:%S}\n"
            f"- Modelo: {model}\n\n"
            f"## Pregunta\n\n{prompt}\n\n"
            f"## Respuesta\n\n{answer.strip()}\n\n"
            f"![captura]({image_path.name})\n",
            encoding="utf-8",
        )
        return note_path

    def _free_stem(self, stem: str) -> str:
        assert self.folder is not None
        candidate, n = stem, 2
        while (self.folder / f"{candidate}.jpg").exists() or (
            self.folder / f"{candidate}.md"
        ).exists():
            candidate = f"{stem}_{n}"
            n += 1
        return candidate
