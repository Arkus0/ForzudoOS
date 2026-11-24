from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QSettings, QThreadPool
from PySide6.QtWidgets import QLabel

from capturaia.config import AppConfig
from capturaia.phone import PhoneServer, PhoneState, lan_ip, markdown_to_html
from capturaia.ui.main_window import MainWindow
from capturaia.ui.phone_dialog import PhoneDialog


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("- **uno** dos\n- tres", "<ul><li><b>uno</b> dos</li><li>tres</li></ul>"),
        ("1. a\n2) b", "<ol><li>a</li><li>b</li></ol>"),
        (
            "Hola *mundo*\nsigue\n\nOtro `x`",
            "<p>Hola <i>mundo</i><br>sigue</p><p>Otro <code>x</code></p>",
        ),
        ("Intro\n- a\nfin", "<p>Intro</p><ul><li>a</li></ul><p>fin</p>"),
        ("## Título\ntexto", "<p><b>Título</b></p><p>texto</p>"),
        (
            "<script>alert(1)</script> & 2*3*4",
            "<p>&lt;script&gt;alert(1)&lt;/script&gt; &amp; 2*3*4</p>",
        ),
        ("", ""),
    ],
)
def test_markdown_to_html(text: str, expected: str) -> None:
    assert markdown_to_html(text) == expected


def test_phone_state_versions_and_connection() -> None:
    now = [10.0]
    state = PhoneState(clock=lambda: now[0])
    assert state.connected() is None
    assert state.publish({"cards": [], "health": {}, "alert": ""})
    assert not state.publish({"cards": [], "health": {}, "alert": ""})  # sin cambios
    assert state.version == 1
    full = json.loads(state.snapshot(None))
    assert full["version"] == 1
    assert "cards" in full
    assert json.loads(state.snapshot(1)) == {"version": 1}  # el móvil ya lo tiene
    assert state.connected() is True
    now[0] += 5
    assert state.connected() is False


def _get(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, b""


def test_phone_server_serves_page_and_state() -> None:
    state = PhoneState()
    server = PhoneServer(state, "clave123", 0, font_px=30)
    server.start()
    try:
        base = f"http://127.0.0.1:{server.port}"
        code, page = _get(f"{base}/clave123/")
        assert code == 200
        assert b'load("capturaia-font", 30)' in page
        assert _get(f"{base}/clave123")[0] == 200
        assert _get(f"{base}/otra/")[0] == 404  # sin la clave no se ve nada
        assert _get(f"{base}/")[0] == 404

        state.publish({"cards": [{"title": "T", "html": "<p>x</p>"}], "health": {}, "alert": ""})
        code, body = _get(f"{base}/clave123/state?v=-1")
        data = json.loads(body)
        assert data["cards"][0]["title"] == "T"
        assert json.loads(_get(f"{base}/clave123/state?v={data['version']}")[1]) == {
            "version": data["version"]
        }
        assert state.connected() is True
        assert server.url.endswith(f":{server.port}/clave123/")
    finally:
        server.stop()


def test_lan_ip_is_an_ipv4() -> None:
    assert lan_ip().count(".") == 3


class FakeAsker:
    model = "fake"

    def ask_stream(self, jpeg: bytes, prompt: str) -> Any:
        yield "- **Clave** uno\n- dos"


def test_window_publishes_to_phone(qtbot: Any, tmp_path: Path, config: AppConfig) -> None:
    now = [0.0]
    state = PhoneState(clock=lambda: now[0])
    server = PhoneServer(state, "tok", 0, 26)  # no se arranca: basta el estado
    window = MainWindow(
        config,
        asker_factory=FakeAsker,
        thread_pool=QThreadPool(),
        settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat),
        phone=server,
    )
    qtbot.addWidget(window)
    assert window.panel.health("Móvil") is None
    assert window._phone_action.isVisible() or not window.isVisible()

    window.ask(0)
    qtbot.waitUntil(lambda: window.panel.cards[0].done, timeout=5000)
    state.snapshot(None)  # el móvil ya está leyendo
    window.publish_to_phone()
    data = json.loads(state.snapshot(None))
    card = data["cards"][0]
    assert card["title"] == "Explícame esto"
    assert card["html"] == "<ul><li><b>Clave</b> uno</li><li>dos</li></ul>"
    assert card["status"].startswith("Listo")
    assert card["done"] is True
    assert len(data["cards"]) == 1  # en el móvil, solo la última respuesta
    assert data["page"] == 0
    window.handle_action("scroll")  # F10 también pasa página en el móvil
    window.publish_to_phone()
    assert json.loads(state.snapshot(None))["page"] == 1
    assert data["health"]["Móvil"] is True

    now[0] += 10  # el móvil deja de leer (pantalla apagada)
    window.publish_to_phone()
    assert window.panel.health("Móvil") is False
    assert "móvil" in window.panel.alert_text.lower()
    # ...pero ese aviso no se manda al propio móvil; los demás sí.
    window.set_hotkeys_health(False, "no hay teclas activas")
    window.publish_to_phone()
    alert = json.loads(state.snapshot(None))["alert"]
    assert "móvil" not in alert.lower()
    assert "Teclas: no hay teclas activas" in alert
    assert window.phone_usb_url == ""  # sin adb no hay dirección por cable
    window.enable_usb("http://localhost:8765")
    assert window.phone_usb_url == "http://localhost:8765/tok/"
    window._pool.waitForDone(5000)


def test_phone_dialog_has_qr_and_url(qtbot: Any) -> None:
    dialog = PhoneDialog("http://192.168.1.20:8765/abc/")
    qtbot.addWidget(dialog)
    assert not dialog.qr.pixmap().isNull()
    assert "192.168.1.20:8765/abc/" in dialog.url.text()
    texts = [label.text() for label in dialog.findChildren(QLabel)]
    assert any("<code>http://192.168.1.20:8765</code>" in t for t in texts)  # para chrome://flags


def test_page_reports_wake_lock_state() -> None:
    page = PhoneServer(PhoneState(), "t", 0, 26).page().decode("utf-8")
    assert 'id="awake"' in page
    assert "requestFullscreen" in page  # al tocar, pantalla completa
    assert "function fit(" in page  # la letra se ajusta para que quepa la respuesta
    assert "navigator.wakeLock.request" in page
    assert "isSecureContext" in page
