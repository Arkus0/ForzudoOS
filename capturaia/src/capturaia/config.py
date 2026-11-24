"""Carga y validación de la configuración (config.toml)."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

APP_NAME = "capturaia"
BACKENDS = ("qt", "opencv", "image")
THINKING_LEVELS = ("", "minimal", "low", "medium", "high")
MEDIA_RESOLUTIONS = ("", "low", "medium", "high", "ultra_high")
SIDES = ("right", "left")


class ConfigError(Exception):
    """Configuración inválida o ilegible."""


@dataclass(frozen=True)
class GeminiConfig:
    api_key: str = ""
    model: str = "gemini-3.8-flash"
    thinking_level: str = "low"
    media_resolution: str = "high"
    system_instruction: str = ""

    def resolved_api_key(self) -> str:
        """Clave del archivo de config o, si está vacía, de las variables de entorno."""
        return (
            self.api_key.strip()
            or os.environ.get("GEMINI_API_KEY", "").strip()
            or os.environ.get("GOOGLE_API_KEY", "").strip()
        )


@dataclass(frozen=True)
class CaptureConfig:
    backend: str = "qt"
    device: str = ""
    width: int = 1920
    height: int = 1080
    fps: int = 60
    fourcc: str = ""
    image_path: str = ""
    jpeg_quality: int = 90
    max_width: int = 1920


@dataclass(frozen=True)
class HistoryConfig:
    enabled: bool = True
    folder: Path | None = None


@dataclass(frozen=True)
class Preset:
    name: str
    prompt: str
    hotkey: str = ""


@dataclass(frozen=True)
class PresenterConfig:
    start: bool = False
    screen: int = 0
    side: str = "left"
    strip_width: int = 340
    font_size: int = 20
    show_video: bool = False
    toggle_hotkey: str = "<f12>"
    scroll_hotkey: str = "<f10>"


@dataclass(frozen=True)
class PhoneConfig:
    enabled: bool = True
    port: int = 8765
    font_size: int = 40
    usb: bool = True
    adb_path: str = ""


@dataclass(frozen=True)
class AppConfig:
    gemini: GeminiConfig
    capture: CaptureConfig
    history: HistoryConfig
    presets: tuple[Preset, ...]
    presenter: PresenterConfig = PresenterConfig()
    phone: PhoneConfig = PhoneConfig()
    path: Path | None = None


DEFAULT_SYSTEM_INSTRUCTION = """\
Eres el apuntador de un formador que está grabando un curso en directo. Recibes una captura
de su pantalla (normalmente una diapositiva o una página web) y una petición.
Tu respuesta se lee de reojo en una columna estrecha mientras habla, así que:
- Responde siempre en español y MUY breve: como mucho 5 viñetas de pocas palabras
  (unas 50 palabras en total), que pueda decir en voz alta tal cual.
- Pon en **negrita** la palabra clave de cada viñeta.
- Sin introducciones, sin despedidas, sin tablas ni títulos.
Si no estás seguro de un dato (normativa, cifras, plazos, requisitos), dilo claramente en vez
de inventarlo. Si algo no se ve bien en la imagen, dilo."""

DEFAULT_PRESETS = (
    Preset(
        name="Explícame esto",
        hotkey="<f8>",
        prompt=(
            "Explica lo que hay en pantalla en 3 o 4 frases sencillas que pueda decir en voz alta."
        ),
    ),
    Preset(
        name="Pon un ejemplo",
        hotkey="<f9>",
        prompt="Dame un ejemplo práctico y realista de lo que se ve en pantalla, en pocas frases.",
    ),
    Preset(
        name="Datos clave",
        hotkey="<f7>",
        prompt="Dame los 3 datos clave que debería mencionar sobre lo que se ve en pantalla.",
    ),
)

DEFAULTS = AppConfig(
    gemini=GeminiConfig(system_instruction=DEFAULT_SYSTEM_INSTRUCTION),
    capture=CaptureConfig(),
    history=HistoryConfig(),
    presets=DEFAULT_PRESETS,
)


def _q(value: str) -> str:
    """Cadena básica de TOML (las secuencias de escape de JSON son válidas en TOML)."""
    return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007F")


def _q_multiline(value: str) -> str:
    """Cadena multilínea de TOML, legible en el archivo."""
    out = []
    for ch in value.replace("\r\n", "\n"):
        if ch == "\\":
            out.append("\\\\")
        elif ch in "\n\t":
            out.append(ch)
        elif ord(ch) < 0x20 or ch == "\x7f":
            out.append(f"\\u{ord(ch):04X}")
        else:
            out.append(ch)
    text = "".join(out).replace('"""', '""\\"')
    if text.endswith('"'):
        text = text[:-1] + '\\"'
    return f'"""\n{text}\n"""'


def _b(value: bool) -> str:
    return "true" if value else "false"


def _history_folder_text(cfg: AppConfig) -> str:
    folder = cfg.history.folder
    if folder is None or (cfg.path is not None and folder == cfg.path.parent / "capturas"):
        return ""
    return str(folder)


def render_config(cfg: AppConfig) -> str:
    """Escribe la configuración como TOML comentado (el mismo formato que el archivo de ejemplo)."""
    g, c, h, pr, ph = cfg.gemini, cfg.capture, cfg.history, cfg.presenter, cfg.phone
    presets = "\n".join(
        f"[[presets]]\nname = {_q(p.name)}\nhotkey = {_q(p.hotkey)}\nprompt = {_q(p.prompt)}\n"
        for p in cfg.presets
    )
    return f"""\
# Configuración de CapturaIA
# Casi todo se puede cambiar desde la pantalla de inicio de la app. Si editas este archivo a
# mano, reinicia la app para aplicar los cambios.

[gemini]
# Tu clave de Gemini (se rellena desde la pantalla de inicio). Vacío = usar la variable de
# entorno GEMINI_API_KEY. Consigue una clave gratis en https://aistudio.google.com/apikey
api_key = {_q(g.api_key)}

# Modelo de Gemini. Alternativas: "gemini-flash-latest" (siempre el Flash más reciente),
# "gemini-3.5-flash-lite" (más rápido y barato).
model = {_q(g.model)}

# Cuánto "piensa" el modelo antes de responder: minimal, low, medium, high.
# Más alto = mejor razonamiento pero más lento. Vacío = lo que decida el modelo.
thinking_level = {_q(g.thinking_level)}

# Detalle con el que Gemini mira la imagen: low, medium, high, ultra_high.
# "high" va bien para leer textos pequeños de la pantalla. Vacío = por defecto.
media_resolution = {_q(g.media_resolution)}

system_instruction = {_q_multiline(g.system_instruction)}

[capture]
# "qt" (recomendado), "opencv" (alternativa si la capturadora da problemas con "qt"; requiere
# instalar con el extra opencv) o "image" (imagen fija de disco, para pruebas sin capturadora).
backend = {_q(c.backend)}

# Nombre (o parte del nombre) de la capturadora, p. ej. "Elgato" o "USB Video".
# Vacío = el dispositivo de vídeo por defecto. Con backend "opencv" es el índice: "0", "1"...
# Para ver los nombres disponibles: capturaia --list-devices
device = {_q(c.device)}

# Formato que se pide a la capturadora (se elige el más parecido que ofrezca).
width = {c.width}
height = {c.height}
fps = {c.fps}

# Solo backend "opencv": código FOURCC a forzar, p. ej. "MJPG" o "YUY2". Vacío = el de la tarjeta.
fourcc = {_q(c.fourcc)}

# Solo backend "image": ruta de la imagen. Vacío = imagen de prueba generada.
image_path = {_q(c.image_path)}

# Imagen que se envía a Gemini.
jpeg_quality = {c.jpeg_quality}
# Ancho máximo en píxeles (0 = sin reescalar). 1920 conserva el detalle de un 1080p.
max_width = {c.max_width}

[history]
# Guarda cada captura (.jpg) con su pregunta y respuesta (.md).
enabled = {_b(h.enabled)}
# Vacío = carpeta "capturas" junto a este archivo.
folder = {_q(_history_folder_text(cfg))}

# Preguntas prefijadas. Cada una con su tecla global (funciona aunque la app no tenga el foco).
# Formato de teclas: "<f8>", "<ctrl>+<alt>+g", "<shift>+<f9>"...
# Truco: F13-F24 no existen en los teclados normales pero sí se pueden asignar en un
# Stream Deck o macro pad, y así nunca chocan con otros programas.

{presets}
[presenter]
# Modo presentación (F12 para entrar/salir; dentro, Esc también sale). Ocupa un monitor del
# PC2 a pantalla completa, en negro, con una franja de respuestas en letra grande.
#
# Por defecto es el "modo atril": trabajas en tu monitor de siempre (directo del portátil) y
# el monitor del PC2, puesto al lado, solo enseña la franja pegada a ese lado. Así basta un
# vistazo corto y no dependes del PC2 para ver ni para clicar.
#
# true = arrancar directamente en este modo (también: capturaia --presentar).
start = {_b(pr.start)}
# Monitor del PC2 donde ponerlo: 1, 2, 3... (0 = el monitor donde esté la ventana; la app
# recuerda dónde la dejaste).
screen = {pr.screen}
# Lado de la franja: el que queda pegado a tu monitor de trabajo. Si el monitor del PC2 está
# a la DERECHA del tuyo, la franja va a la izquierda ("left"), y al revés.
side = {_q(pr.side)}
# Ancho de la franja en píxeles.
strip_width = {pr.strip_width}
# Tamaño de letra de las respuestas (puntos).
font_size = {pr.font_size}
# false = solo la franja (modo atril, recomendado).
# true = además, la imagen del PC1 en el resto de la pantalla (para mirar ese monitor en vez
#        del tuyo; la imagen sale algo más pequeña y con un pequeño retraso). En un monitor
#        panorámico la franja se queda con todo el hueco que sobra.
show_video = {_b(pr.show_video)}
# Teclas globales: entrar/salir del modo y pasar página en la franja (al final vuelve arriba).
toggle_hotkey = {_q(pr.toggle_hotkey)}
scroll_hotkey = {_q(pr.scroll_hotkey)}

[phone]
# Ver las respuestas en el móvil (por ejemplo, en un cuello de cisne junto a tu monitor).
# CapturaIA abre una página que el móvil abre en el navegador, sin instalar nada y sin pasar
# por servidores de fuera. La dirección y un código QR están en Archivo ▸ Conectar el móvil.
enabled = {_b(ph.enabled)}
# Puerto de la página (cámbialo solo si otro programa ya usa este).
port = {ph.port}
# Tamaño de letra máximo en el móvil, en píxeles (luego se ajusta desde el propio móvil).
font_size = {ph.font_size}
# Móvil por cable USB o emparejado sin cable (recomendado): la página se abre como
# http://localhost, la dirección no cambia nunca. Necesita adb (Android SDK Platform-Tools) y
# la depuración USB o inalámbrica activada en el móvil. Sin adb, se usa la wifi con la IP.
usb = {_b(ph.usb)}
# Ruta de adb.exe. Vacío = buscarlo en el PATH y en la carpeta platform-tools junto a la app.
adb_path = {_q(ph.adb_path)}
"""


DEFAULT_CONFIG_TEXT = render_config(DEFAULTS)


def save_config(cfg: AppConfig, path: Path | None = None) -> Path:
    """Guarda la configuración (deja una copia del archivo anterior en config.toml.bak)."""
    path = path or cfg.path or default_config_path()
    if not cfg.presets:
        msg = "Hace falta al menos una pregunta."
        raise ConfigError(msg)
    text = render_config(replace(cfg, path=path))
    parse_config(tomllib.loads(text), path=path)  # nunca se guarda algo que no se pueda leer
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return path


def default_config_dir() -> Path:
    """%APPDATA%\\capturaia en Windows, ~/.config/capturaia en el resto."""
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / APP_NAME
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_NAME


def default_config_path() -> Path:
    env = os.environ.get("CAPTURAIA_CONFIG")
    return Path(env) if env else default_config_dir() / "config.toml"


def ensure_config_file(path: Path) -> bool:
    """Crea el archivo con la configuración por defecto si no existe. Devuelve True si lo creó."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_CONFIG_TEXT, encoding="utf-8")
    return True


def load_config(path: Path | None = None, *, create: bool = True) -> AppConfig:
    """Lee config.toml (creándolo si hace falta) y lo valida."""
    path = path or default_config_path()
    if create:
        ensure_config_file(path)
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        msg = f"No existe el archivo de configuración: {path}"
        raise ConfigError(msg) from exc
    except tomllib.TOMLDecodeError as exc:
        msg = f"Error de sintaxis en {path}: {exc}"
        raise ConfigError(msg) from exc
    return parse_config(raw, path=path)


def parse_config(raw: dict[str, Any], *, path: Path | None = None) -> AppConfig:
    defaults = tomllib.loads(DEFAULT_CONFIG_TEXT)
    gemini = _section(raw, defaults, "gemini")
    capture = _section(raw, defaults, "capture")
    history = _section(raw, defaults, "history")

    gemini_cfg = GeminiConfig(
        api_key=_str(gemini, "api_key"),
        model=_str(gemini, "model").strip(),
        thinking_level=_choice(gemini, "thinking_level", THINKING_LEVELS),
        media_resolution=_choice(gemini, "media_resolution", MEDIA_RESOLUTIONS),
        system_instruction=_str(gemini, "system_instruction").strip(),
    )
    if not gemini_cfg.model:
        msg = "[gemini] model no puede estar vacío."
        raise ConfigError(msg)

    capture_cfg = CaptureConfig(
        backend=_choice(capture, "backend", BACKENDS),
        device=str(capture.get("device", "")).strip(),
        width=_int(capture, "width", 16, 16384),
        height=_int(capture, "height", 16, 16384),
        fps=_int(capture, "fps", 1, 1000),
        fourcc=_str(capture, "fourcc").strip().upper(),
        image_path=_str(capture, "image_path").strip(),
        jpeg_quality=_int(capture, "jpeg_quality", 1, 100),
        max_width=_int(capture, "max_width", 0, 16384),
    )
    if capture_cfg.fourcc and len(capture_cfg.fourcc) != 4:
        msg = "[capture] fourcc debe tener 4 caracteres (p. ej. MJPG) o estar vacío."
        raise ConfigError(msg)

    folder_text = _str(history, "folder").strip()
    if folder_text:
        folder = Path(folder_text).expanduser()
    elif path is not None:
        folder = path.parent / "capturas"
    else:
        folder = None
    enabled = history.get("enabled", True)
    if not isinstance(enabled, bool):
        msg = "[history] enabled debe ser true o false."
        raise ConfigError(msg)
    history_cfg = HistoryConfig(enabled=enabled, folder=folder)

    raw_presets = raw.get("presets", defaults["presets"])
    if not isinstance(raw_presets, list) or not raw_presets:
        msg = "Hace falta al menos un [[presets]] con name y prompt."
        raise ConfigError(msg)
    presets = tuple(_preset(item, i) for i, item in enumerate(raw_presets, start=1))

    presenter = _section(raw, defaults, "presenter")
    if "min_strip_width" in raw.get("presenter", {}):  # nombre antiguo
        presenter["strip_width"] = presenter.pop("min_strip_width")
    presenter_cfg = PresenterConfig(
        start=_bool(presenter, "start"),
        screen=_int(presenter, "screen", 0, 16),
        side=_choice(presenter, "side", SIDES),
        strip_width=_int(presenter, "strip_width", 150, 4000),
        font_size=_int(presenter, "font_size", 8, 96),
        show_video=_bool(presenter, "show_video"),
        toggle_hotkey=_str(presenter, "toggle_hotkey").strip().lower(),
        scroll_hotkey=_str(presenter, "scroll_hotkey").strip().lower(),
    )

    return AppConfig(
        gemini=gemini_cfg,
        capture=capture_cfg,
        history=history_cfg,
        presenter=presenter_cfg,
        phone=_phone(_section(raw, defaults, "phone")),
        presets=presets,
        path=path,
    )


def _section(raw: dict[str, Any], defaults: dict[str, Any], name: str) -> dict[str, Any]:
    value = raw.get(name, {})
    if not isinstance(value, dict):
        msg = f"[{name}] debe ser una sección."
        raise ConfigError(msg)
    return {**defaults[name], **value}


def _str(section: dict[str, Any], key: str) -> str:
    value = section.get(key, "")
    if not isinstance(value, str):
        msg = f"'{key}' debe ser texto entre comillas."
        raise ConfigError(msg)
    return value


def _phone(section: dict[str, Any]) -> PhoneConfig:
    return PhoneConfig(
        enabled=_bool(section, "enabled"),
        port=_int(section, "port", 1024, 65535),
        font_size=_int(section, "font_size", 12, 90),
        usb=_bool(section, "usb"),
        adb_path=_str(section, "adb_path").strip(),
    )


def _bool(section: dict[str, Any], key: str) -> bool:
    value = section.get(key)
    if not isinstance(value, bool):
        msg = f"'{key}' debe ser true o false."
        raise ConfigError(msg)
    return value


def _int(section: dict[str, Any], key: str, low: int, high: int) -> int:
    value = section.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        msg = f"'{key}' debe ser un número entero entre {low} y {high}."
        raise ConfigError(msg)
    return value


def _choice(section: dict[str, Any], key: str, options: tuple[str, ...]) -> str:
    value = _str(section, key).strip().lower()
    if value not in options:
        shown = ", ".join(f'"{o}"' for o in options)
        msg = f"'{key}' debe ser uno de: {shown}."
        raise ConfigError(msg)
    return value


def _preset(item: object, index: int) -> Preset:
    if not isinstance(item, dict):
        msg = f"El preset nº {index} no es válido."
        raise ConfigError(msg)
    name = item.get("name", "")
    prompt = item.get("prompt", "")
    hotkey = item.get("hotkey", "")
    if not all(isinstance(v, str) for v in (name, prompt, hotkey)):
        msg = f"El preset nº {index}: name, prompt y hotkey deben ser texto."
        raise ConfigError(msg)
    if not name.strip() or not prompt.strip():
        msg = f"El preset nº {index} necesita name y prompt."
        raise ConfigError(msg)
    return Preset(name=name.strip(), prompt=prompt.strip(), hotkey=hotkey.strip().lower())
