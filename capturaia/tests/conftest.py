from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest

from capturaia.config import DEFAULT_CONFIG_TEXT, AppConfig, load_config


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("CAPTURAIA_CONFIG", raising=False)


@pytest.fixture
def config(tmp_path: Path) -> AppConfig:
    """Config por defecto pero con la fuente de imagen fija (no hay capturadora en los tests)."""
    path = tmp_path / "config.toml"
    path.write_text(
        DEFAULT_CONFIG_TEXT.replace('backend = "qt"', 'backend = "image"'), encoding="utf-8"
    )
    return load_config(path)
