from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from capturaia import usb_bridge
from capturaia.ui.phone_dialog import PairDialog, PhoneDialog
from capturaia.usb_bridge import (
    UsbBridge,
    find_adb,
    pair,
    parse_devices,
    parse_mdns_connect,
)

DEVICES_OK = "List of devices attached\n28041FDH2000AB\tdevice\n\n"


def test_parse_devices() -> None:
    assert parse_devices("List of devices attached\n\n") == {}
    assert parse_devices(DEVICES_OK) == {"28041FDH2000AB": "device"}
    out = "* daemon started successfully\nList of devices attached\nA\tunauthorized\nB\toffline\n"
    assert parse_devices(out) == {"A": "unauthorized", "B": "offline"}


class FakeAdb:
    """Simula adb: lista de dispositivos y reglas de `adb reverse`."""

    def __init__(self, devices: str = DEVICES_OK, *, reverse_works: bool = True) -> None:
        self.devices = devices
        self.rules: set[str] = set()
        self.reverse_works = reverse_works
        self.calls: list[list[str]] = []

    def __call__(self, args: Sequence[str]) -> str:
        args = list(args)
        self.calls.append(args)
        if args[1:] == ["devices"]:
            return self.devices
        if args[-2:] == ["reverse", "--list"]:
            return "".join(f"UsbFfs tcp:{r} tcp:{r}\n" for r in sorted(self.rules))
        if "reverse" in args and self.reverse_works:
            self.rules.add(args[-1].removeprefix("tcp:"))
            return ""
        return ""


def test_bridge_sets_up_reverse_once(qapp: object) -> None:
    adb = FakeAdb()
    bridge = UsbBridge("adb", 8765, runner=adb)
    seen: list[tuple[str, Any]] = []
    bridge.status.connect(lambda msg, ok: seen.append((msg, ok)))
    message, ok = bridge.check()
    assert ok is True
    assert "localhost:8765" in message
    assert ["adb", "-s", "28041FDH2000AB", "reverse", "tcp:8765", "tcp:8765"] in adb.calls
    calls = len(adb.calls)
    bridge.check()  # ya está: no lo vuelve a crear ni repite el aviso
    assert not any(c[-2:] == ["tcp:8765", "tcp:8765"] for c in adb.calls[calls:])
    assert len(seen) == 1


@pytest.mark.parametrize(
    ("devices", "reverse_works", "ok", "fragment"),
    [
        ("List of devices attached\n\n", True, None, "no conectado"),
        ("List of devices attached\nX\tunauthorized\n", True, False, "Permitir depuración USB"),
        ("List of devices attached\nX\toffline\n", True, False, "no responde"),
        (DEVICES_OK, False, False, "No se pudo preparar"),
    ],
)
def test_bridge_problems(
    qapp: object, devices: str, reverse_works: bool, ok: bool | None, fragment: str
) -> None:
    bridge = UsbBridge("adb", 8765, runner=FakeAdb(devices, reverse_works=reverse_works))
    message, result = bridge.check()
    assert result is ok
    assert fragment in message


def test_bridge_survives_adb_errors(qapp: object) -> None:
    def broken(_args: Sequence[str]) -> str:
        raise subprocess.TimeoutExpired("adb", 10)

    message, ok = UsbBridge("adb", 8765, runner=broken).check()
    assert ok is False
    assert "adb" in message


def test_find_adb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = tmp_path / "adb"
    fake.write_text("")
    assert find_adb(str(fake)) == str(fake)
    assert find_adb(str(tmp_path / "no-existe")) is None

    monkeypatch.setattr(usb_bridge.shutil, "which", lambda _name: None)
    monkeypatch.setattr(usb_bridge, "adb_candidates", lambda: [tmp_path / "x" / "adb", fake])
    assert find_adb() == str(fake)
    monkeypatch.setattr(usb_bridge, "adb_candidates", lambda: [])
    assert find_adb() is None
    monkeypatch.setattr(usb_bridge.shutil, "which", lambda _name: "/usr/bin/adb")
    assert find_adb() == "/usr/bin/adb"


def test_dialog_prefers_usb(qtbot: Any) -> None:
    dialog = PhoneDialog(
        "http://192.168.1.20:8765/abc/",
        usb_url="http://localhost:8765/abc/",
        usb_status="Móvil conectado por USB",
    )
    qtbot.addWidget(dialog)
    assert "localhost:8765/abc/" in dialog.url.text()  # el QR y el enlace grande son el de USB
    texts = " ".join(label.text() for label in dialog.findChildren(type(dialog.url)))
    assert "192.168.1.20:8765/abc/" in texts  # la wifi queda como alternativa
    assert "Móvil conectado por USB" in texts


MDNS = (
    "List of discovered mdns services\n"
    "adb-28041FDH2000AB-RkN8Ut\t_adb-tls-pairing._tcp\t192.168.1.30:41111\n"
    "adb-28041FDH2000AB-RkN8Ut\t_adb-tls-connect._tcp\t192.168.1.30:37099\n"
)


def test_parse_mdns_connect() -> None:
    assert parse_mdns_connect(MDNS) == ["192.168.1.30:37099"]  # solo el de conectar
    assert parse_mdns_connect("List of discovered mdns services\n") == []


class WirelessAdb(FakeAdb):
    """Móvil emparejado sin cable: aparece al hacer `adb connect` a lo anunciado por mDNS."""

    def __init__(self) -> None:
        super().__init__("List of devices attached\n\n")

    def __call__(self, args: Sequence[str]) -> str:
        args = list(args)
        if args[1:3] == ["mdns", "services"]:
            self.calls.append(args)
            return MDNS
        if args[1] == "connect":
            self.calls.append(args)
            self.devices = f"List of devices attached\n{args[2]}\tdevice\n"
            return f"connected to {args[2]}"
        return super().__call__(args)


def test_bridge_connects_paired_phone_without_cable(qapp: object) -> None:
    adb = WirelessAdb()
    message, ok = UsbBridge("adb", 8765, runner=adb).check()
    assert ["adb", "connect", "192.168.1.30:37099"] in adb.calls
    assert ok is True
    assert "sin cable" in message
    assert ["adb", "-s", "192.168.1.30:37099", "reverse", "tcp:8765", "tcp:8765"] in adb.calls


@pytest.mark.parametrize(
    ("address", "code", "output", "ok", "fragment"),
    [
        (
            "192.168.1.30:41111",
            "123456",
            "Successfully paired to 192.168.1.30:41111",
            True,
            "Emparejado",
        ),
        (
            "192.168.1.30:41111",
            "000000",
            "Failed: Wrong password or connection was dropped.",
            False,
            "Wrong password",
        ),
        ("sin-puerto", "123456", "", False, "IP:puerto"),
        ("192.168.1.30:41111", "abc", "", False, "código"),
    ],
)
def test_pair(address: str, code: str, output: str, ok: bool, fragment: str) -> None:
    calls: list[list[str]] = []

    def runner(args: Sequence[str]) -> str:
        calls.append(list(args))
        return output

    result, message = pair("adb", address, code, runner)
    assert result is ok
    assert fragment in message
    if ok:
        assert calls == [["adb", "pair", address, code]]


def test_pair_dialog(qtbot: Any) -> None:
    dialog = PairDialog("adb", runner=lambda _args: "Successfully paired to 1.2.3.4:5")
    qtbot.addWidget(dialog)
    dialog.address.setText("1.2.3.4:5")
    dialog.code.setText("123456")
    assert dialog.do_pair() is True
    assert "Emparejado" in dialog.result.text()
