"""Cliente mínimo de Gemini: imagen + pregunta -> respuesta en streaming."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol

from capturaia.config import GeminiConfig


class GeminiError(Exception):
    """Error con un mensaje apto para mostrar al usuario."""


class Asker(Protocol):
    model: str

    def ask_stream(self, jpeg: bytes, prompt: str) -> Iterator[str]: ...


class GeminiClient:
    def __init__(self, config: GeminiConfig, *, client: Any = None) -> None:
        self.config = config
        self.model = config.model
        if client is None:
            api_key = config.resolved_api_key()
            if not api_key:
                msg = (
                    "Falta la API key de Gemini. Ponla en la variable de entorno GEMINI_API_KEY "
                    "o en [gemini] api_key del archivo de configuración. "
                    "Puedes conseguir una gratis en https://aistudio.google.com/apikey"
                )
                raise GeminiError(msg)
            from google import genai  # import diferido: tarda en cargar  # noqa: PLC0415

            client = genai.Client(api_key=api_key)
        self._client = client

    def _generation_config(self) -> Any:
        from google.genai import types  # noqa: PLC0415

        kwargs: dict[str, Any] = {}
        if self.config.system_instruction:
            kwargs["system_instruction"] = self.config.system_instruction
        if self.config.thinking_level:
            kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_level=self.config.thinking_level.upper()
            )
        return types.GenerateContentConfig(**kwargs)

    def _image_part(self, jpeg: bytes) -> Any:
        from google.genai import types  # noqa: PLC0415

        resolution = None
        if self.config.media_resolution:
            resolution = f"MEDIA_RESOLUTION_{self.config.media_resolution.upper()}"
        return types.Part.from_bytes(data=jpeg, mime_type="image/jpeg", media_resolution=resolution)

    def ask_stream(self, jpeg: bytes, prompt: str) -> Iterator[str]:
        """Envía la imagen y la pregunta; va devolviendo el texto según llega."""
        from google.genai import errors  # noqa: PLC0415

        try:
            stream = self._client.models.generate_content_stream(
                model=self.model,
                contents=[self._image_part(jpeg), prompt],
                config=self._generation_config(),
            )
            for chunk in stream:
                text = _chunk_text(chunk)
                if text:
                    yield text
        except errors.APIError as exc:
            raise GeminiError(describe_api_error(exc, self.model)) from exc
        except GeminiError:
            raise
        except Exception as exc:
            msg = f"No se pudo contactar con Gemini ({type(exc).__name__}: {exc})"
            raise GeminiError(msg) from exc


def _chunk_text(chunk: Any) -> str:
    """Texto de un trozo de respuesta, ignorando partes que no son texto ni pensamientos."""
    candidates = getattr(chunk, "candidates", None) or []
    if not candidates:
        return getattr(chunk, "text", None) or ""
    content = getattr(candidates[0], "content", None)
    parts = getattr(content, "parts", None) or []
    return "".join(
        part.text
        for part in parts
        if getattr(part, "text", None) and not getattr(part, "thought", False)
    )


def describe_api_error(exc: Any, model: str) -> str:
    code = getattr(exc, "code", None)
    detail = getattr(exc, "message", None) or str(exc)
    if code in (401, 403) or (code == 400 and "API key" in detail):
        return f"La API key no es válida o no tiene permiso. ({detail})"
    if code == 404:
        return f"El modelo «{model}» no existe o no está disponible para tu clave. ({detail})"
    if code == 429:
        return f"Has llegado al límite de peticiones de Gemini. Espera un poco. ({detail})"
    if code == 400:
        return f"Gemini rechazó la petición. ({detail})"
    if isinstance(code, int) and code >= 500:
        return f"Gemini no responde ahora mismo (error {code}). Prueba otra vez. ({detail})"
    return f"Error de Gemini {code}: {detail}"
