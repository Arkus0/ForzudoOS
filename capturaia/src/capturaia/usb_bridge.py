"""Móvil por cable USB o por depuración inalámbrica: la página se abre como http://localhost.

Con `adb reverse`, el móvil envía lo que pida a su propio localhost:PUERTO al PC2, por el cable
o por la conexión de depuración inalámbrica (emparejada una vez con un código). Así la dirección
no cambia nunca y Chrome la trata como página segura (el bloqueo de pantalla encendida funciona
sin tocar chrome://flags).

Hace falta `adb` (Android SDK Platform-Tools, de Google) y la «Depuración USB» activada en el
móvil. Si no hay adb, simplemente no se usa y el móvil sigue pudiendo ir por wifi.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable, Sequence
from pathlib import Path

from PySide6.QtCore import QObject, Signal

Runner = Callable[[Sequence[str]], str]

APP_DIR = Path(__file__).resolve().parents[2]  # carpeta capturaia/


def adb_candidates() -> list[Path]:
    exe = "adb.exe" if sys.platform == "win32" else "adb"
    places = [APP_DIR / "platform-tools", Path.home() / "platform-tools"]
    if sys.platform == "win32":
        places += [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools",
            Path("C:/platform-tools"),
        ]
    else:
        places += [Path.home() / "Android" / "Sdk" / "platform-tools"]
    return [place / exe for place in places]


def find_adb(configured: str = "") -> str | None:
    """Ruta de adb: la configurada, la del PATH o una de las carpetas habituales."""
    if configured:
        return configured if Path(configured).is_file() else None
    found = shutil.which("adb")
    if found:
        return found
    return next((str(path) for path in adb_candidates() if path.is_file()), None)


def run_adb(args: Sequence[str]) -> str:
    """Ejecuta adb sin abrir ventanas de consola y devuelve su salida."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(
        list(args), capture_output=True, text=True, timeout=10, creationflags=flags, check=False
    )
    return (result.stdout or "") + (result.stderr or "")


def parse_mdns_connect(output: str) -> list[str]:
    """Salida de `adb mdns services` -> direcciones "IP:puerto" de móviles para conectar."""
    found = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 3 and "_adb-tls-connect" in parts[1] and ":" in parts[2]:
            found.append(parts[2])
    return found


def pair(adb: str, host_port: str, code: str, runner: Runner = run_adb) -> tuple[bool, str]:
    """Empareja el móvil por depuración inalámbrica (una sola vez)."""
    host_port, code = host_port.strip(), code.strip()
    if ":" not in host_port or not code.isdigit():
        return False, "Escribe la IP:puerto y el código de 6 cifras que muestra el móvil."
    try:
        output = runner([adb, "pair", host_port, code])
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"No se pudo ejecutar adb ({exc})"
    if "Successfully paired" in output:
        return (
            True,
            "Emparejado. A partir de ahora se conecta solo cuando el móvil esté en la wifi.",
        )
    return False, f"No se pudo emparejar: {output.strip() or 'sin respuesta'}"


def parse_devices(output: str) -> dict[str, str]:
    """Salida de `adb devices` -> {serie: estado} ("device", "unauthorized", "offline"...)."""
    devices = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and not line.startswith(("List of devices", "*")):
            devices[parts[0]] = parts[1]
    return devices


class UsbBridge(QObject):
    """Vigila el cable cada pocos segundos y mantiene activo el `adb reverse`."""

    status = Signal(str, object)  # mensaje, ok (True / False / None = sin móvil)

    def __init__(
        self, adb: str, port: int, *, runner: Runner = run_adb, interval_s: float = 3.0
    ) -> None:
        super().__init__()
        self.adb = adb
        self.port = port
        self._runner = runner
        self._interval = interval_s
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last: tuple[str, bool | None] = ("", None)

    @property
    def url_base(self) -> str:
        return f"http://localhost:{self.port}"

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.check()
            self._stop.wait(self._interval)

    def check(self) -> tuple[str, bool | None]:
        """Una comprobación: detecta el móvil y crea el reenvío si falta."""
        try:
            result = self._check()
        except (OSError, subprocess.SubprocessError) as exc:
            result = (f"No se pudo ejecutar adb ({exc})", False)
        if result != self.last:
            self.last = result
            self.status.emit(*result)
        return result

    def _check(self) -> tuple[str, bool | None]:
        devices = parse_devices(self._runner([self.adb, "devices"]))
        if not devices:
            # ¿Un móvil emparejado sin cable anunciándose en la wifi? Se conecta solo.
            for address in parse_mdns_connect(self._runner([self.adb, "mdns", "services"])):
                self._runner([self.adb, "connect", address])
            devices = parse_devices(self._runner([self.adb, "devices"]))
        if not devices:
            return ("Móvil no conectado (ni por cable ni sin cable)", None)
        if "unauthorized" in devices.values() and "device" not in devices.values():
            return ("Acepta «Permitir depuración USB» en el móvil", False)
        serial = next((s for s, state in devices.items() if state == "device"), None)
        if serial is None:
            return ("El móvil no responde (desconéctalo y vuelve a conectarlo)", False)
        rule = f"tcp:{self.port}"
        existing = self._runner([self.adb, "-s", serial, "reverse", "--list"])
        if rule not in existing:
            self._runner([self.adb, "-s", serial, "reverse", rule, rule])
            existing = self._runner([self.adb, "-s", serial, "reverse", "--list"])
            if rule not in existing:
                return ("No se pudo preparar el móvil", False)
        how = "sin cable" if ":" in serial or "._tcp" in serial else "por cable"
        return (f"Móvil conectado {how}: abre {self.url_base}/…", True)
