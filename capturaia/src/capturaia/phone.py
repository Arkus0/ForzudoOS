"""Página para el móvil: las respuestas en tu wifi de casa, sin pasar por servidores de fuera.

El PC2 sirve una página (http://IP-del-PC2:puerto/<clave>/) que el móvil abre en el navegador.
La página pregunta cada pocos cientos de milisegundos por el estado y lo pinta en letra grande
sobre fondo negro. La clave aleatoria de la dirección evita que otro aparato de la red la lea.
"""

from __future__ import annotations

import html
import json
import re
import socket
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

STALE_AFTER_S = 3.0  # sin peticiones del móvil en este tiempo = móvil desconectado


class PhoneState:
    """Estado compartido entre la interfaz (escribe) y el servidor web (lee). Seguro entre hilos."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._lock = threading.Lock()
        self._clock = clock
        self._version = 0
        self._payload = b'{"version": 0, "cards": [], "health": {}, "alert": ""}'
        self._last_json = ""
        self._last_poll: float | None = None

    def publish(self, data: dict[str, Any]) -> bool:
        """Guarda un estado nuevo. Devuelve True si ha cambiado."""
        body = json.dumps(data, ensure_ascii=False, sort_keys=True)
        with self._lock:
            if body == self._last_json:
                return False
            self._last_json = body
            self._version += 1
            self._payload = json.dumps(
                {**data, "version": self._version}, ensure_ascii=False
            ).encode("utf-8")
            return True

    def snapshot(self, known_version: int | None) -> bytes:
        with self._lock:
            self._last_poll = self._clock()
            if known_version == self._version:
                return json.dumps({"version": self._version}).encode("utf-8")
            return self._payload

    @property
    def version(self) -> int:
        with self._lock:
            return self._version

    def connected(self) -> bool | None:
        """True si el móvil está leyendo, False si leía y ha dejado de hacerlo, None si nunca."""
        with self._lock:
            if self._last_poll is None:
                return None
            return self._clock() - self._last_poll <= STALE_AFTER_S


class PhoneServer:
    def __init__(self, state: PhoneState, token: str, port: int, font_px: int) -> None:
        self.state = state
        self.token = token
        self.port = port
        self.font_px = font_px
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Arranca el servidor en segundo plano. Lanza OSError si el puerto está ocupado."""
        server = ThreadingHTTPServer(("0.0.0.0", self.port), _make_handler(self))
        server.daemon_threads = True
        self.port = server.server_address[1]
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    @property
    def url(self) -> str:
        return f"http://{lan_ip()}:{self.port}/{self.token}/"

    def page(self) -> bytes:
        return PAGE.replace("__FONT_PX__", str(self.font_px)).encode("utf-8")


def _make_handler(server: PhoneServer) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parts = urlsplit(self.path)
            base = f"/{server.token}"
            if parts.path in (base, base + "/"):
                self._send(200, "text/html; charset=utf-8", server.page())
            elif parts.path == base + "/state":
                raw = parse_qs(parts.query).get("v", [""])[0]
                known = int(raw) if raw.lstrip("-").isdigit() else None
                self._send(200, "application/json; charset=utf-8", server.state.snapshot(known))
            else:
                self._send(404, "text/plain; charset=utf-8", b"No encontrado")

        def _send(self, code: int, content_type: str, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            pass  # sin ruido en la consola

    return Handler


def lan_ip() -> str:
    """IP del PC2 en la red local (no envía nada: solo pregunta qué interfaz usaría)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect(("10.255.255.255", 1))
            return sock.getsockname()[0]
        except OSError:
            return "127.0.0.1"


_BULLET = re.compile(r"^\s*[-*+]\s+(.*)$")
_NUMBERED = re.compile(r"^\s*\d+[.)]\s+(.*)$")


def _inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<i>\1</i>", text)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", text)


def markdown_to_html(text: str) -> str:
    """Markdown mínimo (viñetas, listas numeradas, negrita, cursiva, código) a HTML seguro."""
    out: list[str] = []
    open_list = ""
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            out.append("<p>" + "<br>".join(_inline(line) for line in paragraph) + "</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal open_list
        if open_list:
            out.append(f"</{open_list}>")
            open_list = ""

    for raw in text.splitlines():
        line = raw.rstrip()
        bullet, numbered = _BULLET.match(line), _NUMBERED.match(line)
        if bullet or numbered:
            flush_paragraph()
            kind = "ul" if bullet else "ol"
            if open_list != kind:
                close_list()
                out.append(f"<{kind}>")
                open_list = kind
            item = (bullet or numbered).group(1)  # type: ignore[union-attr]
            out.append(f"<li>{_inline(item)}</li>")
        elif not line.strip():
            flush_paragraph()
            close_list()
        else:
            close_list()
            heading = line.lstrip("#").strip() if line.startswith("#") else None
            if heading is not None:
                flush_paragraph()
                out.append(f"<p><b>{_inline(heading)}</b></p>")
            else:
                paragraph.append(line.strip())
    flush_paragraph()
    close_list()
    return "".join(out)


PAGE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#000000">
<title>CapturaIA</title>
<style>
  :root { --font: __FONT_PX__px; --dim: 0.8; }
  html, body { margin: 0; background: #000; color: #d6d6d6; height: 100%; }
  body { font: var(--font)/1.35 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
         -webkit-text-size-adjust: 100%; }
  main { padding: 12px 14px 64px; opacity: var(--dim); }
  #alert { display: none; background: #7a1d1d; color: #fff; font-weight: 600;
           padding: 10px 12px; border-radius: 8px; margin-bottom: 10px; font-size: 0.75em; }
  .card { border-left: 4px solid #2f6fb3; padding: 4px 0 4px 12px; margin-bottom: 18px; }
  .card.old { border-left-color: #333; opacity: 0.45; font-size: 0.8em; }
  .title { color: #7fb4ea; font-size: 0.65em; font-weight: 600; }
  .status { color: #8a8f96; font-size: 0.5em; margin-top: 4px; }
  .error .body { color: #ff8a8a; }
  .body p { margin: 0.2em 0 0.5em; }
  .body ul, .body ol { margin: 0.2em 0 0.5em; padding-left: 1.1em; }
  .body li { margin-bottom: 0.35em; }
  .body b { color: #fff; }
  #empty { color: #6f747b; font-size: 0.7em; }
  #bar { position: fixed; left: 0; right: 0; bottom: 0; display: flex; gap: 8px;
         align-items: center; padding: 8px 12px calc(8px + env(safe-area-inset-bottom));
         background: #000; opacity: 0.5; font-size: 14px; }
  #bar button { background: #111; color: #9a9a9a; border: 1px solid #333; border-radius: 6px;
                font-size: 15px; padding: 6px 10px; white-space: nowrap; }
  #health { margin-left: auto; color: #8a8f96; }
  .dot { font-size: 16px; }
  #offline { display: none; position: fixed; top: 0; left: 0; right: 0; background: #7a1d1d;
             color: #fff; text-align: center; padding: 8px; font: 600 16px system-ui; }
</style>
</head>
<body>
<div id="offline">Sin conexión con CapturaIA (¿PC2 encendido y misma wifi?)</div>
<main>
  <div id="alert"></div>
  <div id="cards"><p id="empty">Esperando la primera pregunta…</p></div>
</main>
<div id="bar">
  <button id="fminus" aria-label="Letra más pequeña">A−</button>
  <button id="fplus" aria-label="Letra más grande">A+</button>
  <button id="dminus" aria-label="Menos brillo">☀−</button>
  <button id="dplus" aria-label="Más brillo">☀+</button>
  <span id="health"></span>
</div>
<script>
(function () {
  var base = location.pathname.replace(/\\/$/, "");
  var version = -1, failures = 0;
  var root = document.documentElement;
  function load(key, fallback) {
    try { var v = localStorage.getItem(key); return v === null ? fallback : parseFloat(v); }
    catch (e) { return fallback; }
  }
  function save(key, value) { try { localStorage.setItem(key, String(value)); } catch (e) {} }
  var font = load("capturaia-font", __FONT_PX__), dim = load("capturaia-dim", 0.8);
  function apply() {
    root.style.setProperty("--font", font + "px");
    root.style.setProperty("--dim", dim);
  }
  apply();
  function step(kind, delta) {
    if (kind === "font") { font = Math.max(14, Math.min(60, font + delta)); save("capturaia-font", font); }
    else { dim = Math.max(0.2, Math.min(1, Math.round((dim + delta) * 10) / 10)); save("capturaia-dim", dim); }
    apply();
  }
  document.getElementById("fminus").onclick = function () { step("font", -2); };
  document.getElementById("fplus").onclick = function () { step("font", 2); };
  document.getElementById("dminus").onclick = function () { step("dim", -0.1); };
  document.getElementById("dplus").onclick = function () { step("dim", 0.1); };

  // Intento de mantener la pantalla encendida (solo funciona en algunos navegadores).
  var lock = null;
  function keepAwake() {
    if (navigator.wakeLock && document.visibilityState === "visible") {
      navigator.wakeLock.request("screen").then(function (l) { lock = l; }).catch(function () {});
    }
  }
  document.addEventListener("visibilitychange", keepAwake);
  keepAwake();

  var colors = { "true": "#3fb950", "false": "#f85149", "null": "#8b949e" };
  function esc(s) { var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
  function render(state) {
    var alertBox = document.getElementById("alert");
    alertBox.textContent = state.alert || "";
    alertBox.style.display = state.alert ? "block" : "none";
    var html = "";
    (state.cards || []).forEach(function (c, i) {
      html += '<div class="card' + (i ? " old" : "") + (c.error ? " error" : "") + '">' +
        '<div class="title">' + esc(c.title) + '</div>' +
        '<div class="body">' + c.html + '</div>' +
        '<div class="status">' + esc(c.status) + '</div></div>';
    });
    document.getElementById("cards").innerHTML = html || '<p id="empty">Esperando la primera pregunta…</p>';
    var h = "";
    Object.keys(state.health || {}).forEach(function (name) {
      h += '<span style="white-space:nowrap"><span class="dot" style="color:' +
        colors[String(state.health[name])] + '">●</span> ' + esc(name) + "</span> ";
    });
    document.getElementById("health").innerHTML = h;
  }
  function poll() {
    fetch(base + "/state?v=" + version, { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (state) {
        failures = 0;
        document.getElementById("offline").style.display = "none";
        if (state.cards && state.version !== version) { version = state.version; render(state); }
      })
      .catch(function () {
        failures += 1;
        if (failures >= 3) { document.getElementById("offline").style.display = "block"; }
      })
      .then(function () { setTimeout(poll, 400); });
  }
  poll();
})();
</script>
</body>
</html>
"""
