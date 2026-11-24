"""Cálculo del reparto de pantalla en el modo presentación."""

from __future__ import annotations


def presenter_split(
    total_w: int, total_h: int, frame_w: int, frame_h: int, min_strip: int
) -> tuple[int, int]:
    """Devuelve (ancho_video, ancho_franja).

    La imagen del PC1 ocupa toda la altura si así queda sitio para la franja mínima (p. ej. un
    16:9 en un monitor 21:9: la franja se queda con todo el hueco sobrante). Si no cabe, la
    imagen se estrecha lo justo; nunca se recorta porque el vídeo mantiene su proporción.
    """
    if total_w <= 0 or total_h <= 0:
        return 0, 0
    min_strip = max(0, min(min_strip, total_w))
    aspect = frame_w / frame_h if frame_w > 0 and frame_h > 0 else 16 / 9
    video_w = min(round(total_h * aspect), total_w - min_strip)
    video_w = max(video_w, 0)
    return video_w, total_w - video_w
