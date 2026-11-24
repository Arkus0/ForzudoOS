from __future__ import annotations

import pytest

from capturaia.capture.base import FpsMeter
from capturaia.ui.layout import presenter_split


@pytest.mark.parametrize(
    ("screen", "frame", "min_strip", "expected"),
    [
        # Monitor 21:9: el 16:9 se ve a altura completa y la franja se queda el hueco.
        ((2560, 1080), (1920, 1080), 380, (1920, 640)),
        ((3440, 1440), (1920, 1080), 380, (2560, 880)),
        # Monitor 16:9: la imagen se estrecha lo justo para dejar la franja mínima.
        ((1920, 1080), (1920, 1080), 380, (1540, 380)),
        # PC1 a 16:10 en monitor 16:9.
        ((1920, 1080), (1920, 1200), 200, (1720, 200)),
        # Monitor muy ancho: nunca más ancho que la proporción del vídeo.
        ((5120, 1440), (1920, 1080), 380, (2560, 2560)),
        # Tamaño de frame desconocido: se asume 16:9.
        ((2560, 1080), (0, 0), 380, (1920, 640)),
        # Franja mayor que la pantalla: todo para la franja.
        ((300, 200), (1920, 1080), 500, (0, 300)),
        ((0, 0), (1920, 1080), 380, (0, 0)),
    ],
)
def test_presenter_split(
    screen: tuple[int, int], frame: tuple[int, int], min_strip: int, expected: tuple[int, int]
) -> None:
    assert presenter_split(*screen, *frame, min_strip) == expected


def test_fps_meter() -> None:
    now = [0.0]
    meter = FpsMeter(window_s=2.0, clock=lambda: now[0])
    assert meter.fps() == 0.0
    for _ in range(121):  # 60 fps durante 2 s
        meter.tick()
        now[0] += 1 / 60
    assert meter.fps() == pytest.approx(60, abs=1)
    now[0] += 5  # deja de llegar imagen
    assert meter.fps() == 0.0


def test_compact_markdown_removes_list_indent() -> None:
    from capturaia.ui.answer_panel import compact_markdown  # noqa: PLC0415

    text = "Intro\n- **uno** dos\n  * tres\n1. cuatro\n2) cinco\nfin"
    assert compact_markdown(text) == (
        "Intro\n\n• **uno** dos\n\n• tres\n\n1\\. cuatro\n\n2\\. cinco\n\nfin"
    )
    assert compact_markdown("sin listas") == "sin listas"
