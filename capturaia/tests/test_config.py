from __future__ import annotations

from pathlib import Path

import pytest

from capturaia.config import (
    DEFAULT_CONFIG_TEXT,
    ConfigError,
    GeminiConfig,
    PresenterConfig,
    default_config_path,
    load_config,
)


def test_creates_default_file(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "config.toml"
    config = load_config(path)
    assert path.read_text(encoding="utf-8") == DEFAULT_CONFIG_TEXT
    assert config.path == path
    assert config.capture.backend == "qt"
    assert config.gemini.model
    assert config.gemini.thinking_level == "low"
    assert [p.hotkey for p in config.presets] == ["<f8>", "<f9>", "<f7>"]
    assert config.presenter == PresenterConfig()
    assert config.history.enabled
    assert config.history.folder == path.parent / "capturas"


def test_partial_file_uses_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[gemini]\nmodel = "otro-modelo"\n', encoding="utf-8")
    config = load_config(path)
    assert config.gemini.model == "otro-modelo"
    assert config.capture.width == 1920
    assert len(config.presets) == 3
    assert config.presenter.side == "right"


def test_custom_presets_and_history_folder(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        '[history]\nfolder = "~/mis-capturas"\n'
        '[[presets]]\nname = "Uno"\nhotkey = "<CTRL>+<F13>"\nprompt = "  ¿Qué pasa?  "\n',
        encoding="utf-8",
    )
    config = load_config(path)
    assert len(config.presets) == 1
    preset = config.presets[0]
    assert (preset.name, preset.hotkey, preset.prompt) == ("Uno", "<ctrl>+<f13>", "¿Qué pasa?")
    assert config.history.folder == Path("~/mis-capturas").expanduser()


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ('[capture]\nbackend = "obs"\n', "backend"),
        ("[capture]\njpeg_quality = 0\n", "jpeg_quality"),
        ('[capture]\nwidth = "1920"\n', "width"),
        ('[capture]\nfourcc = "MJ"\n', "fourcc"),
        ('[gemini]\nthinking_level = "turbo"\n', "thinking_level"),
        ('[gemini]\nmodel = " "\n', "model"),
        ("presets = []\n", "preset"),
        ('[[presets]]\nname = "Sin prompt"\n', "prompt"),
        ('[history]\nenabled = "si"\n', "enabled"),
        ("esto no es toml", "sintaxis"),
        ('[presenter]\nside = "arriba"\n', "side"),
        ("[presenter]\nmin_strip_width = 10\n", "min_strip_width"),
        ("[presenter]\nfont_size = 0\n", "font_size"),
        ("[presenter]\nscreen = -1\n", "screen"),
        ('[presenter]\nstart = "si"\n', "start"),
        ("[presenter]\ntoggle_hotkey = 12\n", "toggle_hotkey"),
    ],
)
def test_invalid_values(tmp_path: Path, text: str, fragment: str) -> None:
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError, match=fragment):
        load_config(path)


def test_example_file_matches_default() -> None:
    example = Path(__file__).parent.parent / "config.example.toml"
    assert example.read_text(encoding="utf-8") == DEFAULT_CONFIG_TEXT


def test_missing_file_without_create(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="No existe"):
        load_config(tmp_path / "nada.toml", create=False)


def test_api_key_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    assert GeminiConfig().resolved_api_key() == ""
    monkeypatch.setenv("GOOGLE_API_KEY", "google")
    assert GeminiConfig().resolved_api_key() == "google"
    monkeypatch.setenv("GEMINI_API_KEY", "gemini")
    assert GeminiConfig().resolved_api_key() == "gemini"
    assert GeminiConfig(api_key=" archivo ").resolved_api_key() == "archivo"


def test_config_path_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CAPTURAIA_CONFIG", str(tmp_path / "x.toml"))
    assert default_config_path() == tmp_path / "x.toml"


def test_presenter_section(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        '[presenter]\nstart = true\nscreen = 1\nside = "LEFT"\nmin_strip_width = 500\n'
        'font_size = 28\ntoggle_hotkey = "<F11>"\nscroll_hotkey = ""\n',
        encoding="utf-8",
    )
    presenter = load_config(path).presenter
    assert presenter == PresenterConfig(
        start=True,
        screen=1,
        side="left",
        min_strip_width=500,
        font_size=28,
        toggle_hotkey="<f11>",
        scroll_hotkey="",
    )
