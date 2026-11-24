from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import errors, types

from capturaia.config import GeminiConfig
from capturaia.gemini import GeminiClient, GeminiError, describe_api_error


def _chunk(*parts: tuple[str, bool]) -> Any:
    return SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[SimpleNamespace(text=t, thought=th) for t, th in parts]
                )
            )
        ]
    )


class FakeModels:
    def __init__(self, chunks: list[Any] | None = None, exc: Exception | None = None) -> None:
        self.chunks = chunks or []
        self.exc = exc
        self.calls: list[dict[str, Any]] = []

    def get(self, *, model: str) -> Any:
        if self.exc is not None:
            raise self.exc
        return SimpleNamespace(display_name=f"Modelo {model}")

    def generate_content_stream(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.exc is not None:
            raise self.exc
        yield from self.chunks


def _client(models: FakeModels, **cfg: Any) -> GeminiClient:
    return GeminiClient(GeminiConfig(**cfg), client=SimpleNamespace(models=models))


def test_missing_api_key() -> None:
    with pytest.raises(GeminiError, match="GEMINI_API_KEY"):
        GeminiClient(GeminiConfig())


def test_streams_text_and_skips_thoughts() -> None:
    models = FakeModels([_chunk(("Hola", False), ("pensando", True)), _chunk((" mundo", False))])
    client = _client(models, model="m-1", system_instruction="sé breve")
    assert list(client.ask_stream(b"jpeg", "¿Qué ves?")) == ["Hola", " mundo"]

    call = models.calls[0]
    assert call["model"] == "m-1"
    image, prompt = call["contents"]
    assert isinstance(image, types.Part)
    assert image.inline_data.mime_type == "image/jpeg"
    assert image.inline_data.data == b"jpeg"
    assert image.media_resolution.level == types.PartMediaResolutionLevel.MEDIA_RESOLUTION_HIGH
    assert prompt == "¿Qué ves?"
    config = call["config"]
    assert config.system_instruction == "sé breve"
    assert config.thinking_config.thinking_level == types.ThinkingLevel.LOW


def test_optional_settings_can_be_empty() -> None:
    models = FakeModels([SimpleNamespace(candidates=None, text="solo texto")])
    client = _client(models, thinking_level="", media_resolution="")
    assert list(client.ask_stream(b"x", "p")) == ["solo texto"]
    call = models.calls[0]
    assert call["config"].thinking_config is None
    assert call["config"].system_instruction is None
    assert call["contents"][0].media_resolution is None


def test_api_error_is_translated() -> None:
    exc = errors.ClientError(429, {"error": {"message": "quota", "status": "RESOURCE_EXHAUSTED"}})
    client = _client(FakeModels(exc=exc))
    with pytest.raises(GeminiError, match="límite"):
        list(client.ask_stream(b"x", "p"))


def test_network_error_is_translated() -> None:
    client = _client(FakeModels(exc=ConnectionError("sin red")))
    with pytest.raises(GeminiError, match="No se pudo contactar"):
        list(client.ask_stream(b"x", "p"))


@pytest.mark.parametrize(
    ("code", "message", "fragment"),
    [
        (400, "API key not valid", "API key"),
        (403, "denied", "API key"),
        (404, "not found", "modelo-x"),
        (400, "bad image", "rechazó"),
        (503, "overloaded", "no responde"),
        (418, "teapot", "418"),
    ],
)
def test_describe_api_error(code: int, message: str, fragment: str) -> None:
    exc = SimpleNamespace(code=code, message=message)
    assert fragment in describe_api_error(exc, "modelo-x")


def test_check_validates_key_and_model() -> None:
    assert _client(FakeModels(), model="m-9").check() == "Modelo m-9"
    exc = errors.ClientError(404, {"error": {"message": "no existe", "status": "NOT_FOUND"}})
    with pytest.raises(GeminiError, match="m-9"):
        _client(FakeModels(exc=exc), model="m-9").check()
    with pytest.raises(GeminiError, match="No se pudo contactar"):
        _client(FakeModels(exc=TimeoutError("lento"))).check()
