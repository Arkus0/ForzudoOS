from __future__ import annotations

import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

from capturaia.config import (
    DEFAULT_CONFIG_TEXT,
    ConfigError,
    GeminiConfig,
    PresenterConfig,
    Preset,
    default_config_path,
    load_config,
    parse_config,
    render_config,
    save_config,
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
    assert config.presenter.side == "left"
    assert not config.presenter.show_video


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
        ("[presenter]\nstrip_width = 10\n", "strip_width"),
        ('[presenter]\nshow_video = "no"\n', "show_video"),
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
        '[presenter]\nstart = true\nscreen = 1\nside = "RIGHT"\nstrip_width = 500\n'
        'font_size = 28\nshow_video = true\ntoggle_hotkey = "<F11>"\nscroll_hotkey = ""\n',
        encoding="utf-8",
    )
    presenter = load_config(path).presenter
    assert presenter == PresenterConfig(
        start=True,
        screen=1,
        side="right",
        strip_width=500,
        font_size=28,
        show_video=True,
        toggle_hotkey="<f11>",
        scroll_hotkey="",
    )


def test_old_min_strip_width_name_still_works(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[presenter]\nmin_strip_width = 420\n", encoding="utf-8")
    assert load_config(path).presenter.strip_width == 420


def test_phone_section(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[phone]\nenabled = false\nport = 9000\nfont_size = 30\n", encoding="utf-8")
    phone = load_config(path).phone
    assert (phone.enabled, phone.port, phone.font_size) == (False, 9000, 30)
    assert phone.usb is True
    assert phone.adb_path == ""
    path.write_text("[phone]\nport = 80\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="port"):
        load_config(path)


def test_render_and_parse_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    base = load_config(path)
    tricky = replace(
        base,
        gemini=replace(
            base.gemini,
            api_key="AIza-clave",
            model="gemini-3.5-flash-lite",
            system_instruction='Usa "comillas", barras \\ y """ triples.\nSegunda línea: ñ á ü',
        ),
        presets=(
            Preset('Pregunta "rara"', 'Línea 1\nLínea 2 con "comillas" y \\', "<ctrl>+<f13>"),
            Preset("Otra", "Breve", "<f9>"),
        ),
        history=replace(base.history, folder=tmp_path / "otra carpeta"),
        presenter=replace(base.presenter, side="right", strip_width=420),
        phone=replace(base.phone, port=9000, usb=False),
    )
    text = render_config(tricky)
    again = parse_config(tomllib.loads(text), path=path)
    assert again == tricky


def test_default_history_folder_is_written_empty(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "config.toml")
    assert 'folder = ""' in render_config(cfg)


def test_save_config_keeps_backup_and_validates(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    cfg = load_config(path)
    original = path.read_text(encoding="utf-8")
    new = replace(cfg, gemini=replace(cfg.gemini, api_key="nueva"))
    assert save_config(new) == path
    assert load_config(path).gemini.api_key == "nueva"
    assert (tmp_path / "config.toml.bak").read_text(encoding="utf-8") == original
    assert not (tmp_path / "config.toml.tmp").exists()

    broken = replace(cfg, presets=())
    with pytest.raises(ConfigError):
        save_config(broken)
    assert load_config(path).gemini.api_key == "nueva"  # no se ha tocado
