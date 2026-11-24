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
  :root { --dim: 0.8; }
  html, body { margin: 0; background: #000; color: #d6d6d6; height: 100%; overflow: hidden; }
  body { font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
         -webkit-text-size-adjust: 100%; user-select: none; }
  /* Solo la respuesta: ocupa toda la pantalla y el texto se ajusta para caber. */
  #answer { position: fixed; inset: 0; box-sizing: border-box; overflow-y: auto;
            padding: max(10px, env(safe-area-inset-top)) max(16px, env(safe-area-inset-right))
                     max(10px, env(safe-area-inset-bottom)) max(16px, env(safe-area-inset-left));
            line-height: 1.3; opacity: var(--dim); scrollbar-width: none; scroll-behavior: smooth; }
  #answer::-webkit-scrollbar { display: none; }
  #answer p { margin: 0 0 0.45em; }
  #answer ul, #answer ol { margin: 0 0 0.45em; padding-left: 1.1em; }
  #answer li { margin-bottom: 0.3em; }
  #answer b { color: #fff; }
  #answer.error { color: #ff8a8a; }
  #answer .wait, #answer .hint { color: #6f747b; }
  /* Avisos: solo aparecen si algo falla. */
  #warnings { position: fixed; top: 0; left: 0; right: 0; z-index: 3; }
  #warnings div { display: none; background: #7a1d1d; color: #fff; font: 600 15px system-ui;
                  padding: 6px 12px; text-align: center; }
  #awake-warn { position: fixed; right: 8px; bottom: 6px; z-index: 2; display: none;
                color: #d29922; font: 13px system-ui; opacity: 0.8; }
  /* Controles: aparecen unos segundos al tocar la pantalla. */
  #bar { position: fixed; left: 0; right: 0; bottom: 0; z-index: 4; display: none; gap: 8px;
         flex-wrap: wrap; row-gap: 6px; align-items: center; background: rgba(0, 0, 0, 0.92);
         padding: 8px 12px calc(8px + env(safe-area-inset-bottom)); font-size: 14px;
         color: #8a8f96; border-top: 1px solid #222; }
  #bar.show { display: flex; }
  #bar button { background: #111; color: #9a9a9a; border: 1px solid #333; border-radius: 6px;
                font-size: 15px; padding: 6px 10px; white-space: nowrap; }
  #awake { white-space: nowrap; }
  #health { margin-left: auto; white-space: nowrap; }
  .dot { font-size: 16px; }
</style>
</head>
<body>
<div id="warnings">
  <div id="offline">Sin conexión con CapturaIA (¿PC2 encendido y misma wifi?)</div>
  <div id="alert"></div>
</div>
<main id="answer"><p class="hint">Listo. Pulsa una tecla para preguntar.</p></main>
<div id="awake-warn">La pantalla puede apagarse</div>
<div id="bar">
  <button id="fminus" aria-label="Letra más pequeña">A−</button>
  <button id="fplus" aria-label="Letra más grande">A+</button>
  <button id="dminus" aria-label="Menos brillo">☀−</button>
  <button id="dplus" aria-label="Más brillo">☀+</button>
  <span id="awake"></span>
  <span id="health"></span>
</div>
<script>
(function () {
  var base = location.pathname.replace(/\\/$/, "");
  var answer = document.getElementById("answer");
  var bar = document.getElementById("bar");
  var root = document.documentElement;
  var version = -1, failures = 0, cardId = null, page = null, size = 0, barTimer = null;
  var MIN_FONT = 16;

  function load(key, fallback) {
    try { var v = localStorage.getItem(key); return v === null ? fallback : parseFloat(v); }
    catch (e) { return fallback; }
  }
  function save(key, value) { try { localStorage.setItem(key, String(value)); } catch (e) {} }
  var maxFont = load("capturaia-font", __FONT_PX__), dim = load("capturaia-dim", 0.8);
  root.style.setProperty("--dim", dim);

  // Letra lo más grande posible (hasta el máximo elegido) sin que la respuesta se salga.
  // Durante una misma respuesta solo se reduce, para que no "baile" mientras se escribe.
  function fit(reset) {
    if (reset || !size) { size = maxFont; }
    answer.style.fontSize = size + "px";
    while (answer.scrollHeight > answer.clientHeight + 1 && size > MIN_FONT) {
      size -= 1;
      answer.style.fontSize = size + "px";
    }
  }
  window.addEventListener("resize", function () { fit(true); });

  function step(kind, delta) {
    if (kind === "font") { maxFont = Math.max(MIN_FONT, Math.min(90, maxFont + delta)); save("capturaia-font", maxFont); fit(true); }
    else { dim = Math.max(0.2, Math.min(1, Math.round((dim + delta) * 10) / 10)); save("capturaia-dim", dim); root.style.setProperty("--dim", dim); }
  }
  function button(id, kind, delta) {
    document.getElementById(id).addEventListener("click", function (e) { e.stopPropagation(); step(kind, delta); showBar(); });
  }
  button("fminus", "font", -2); button("fplus", "font", 2);
  button("dminus", "dim", -0.1); button("dplus", "dim", 0.1);

  function showBar() {
    bar.classList.add("show");
    clearTimeout(barTimer);
    barTimer = setTimeout(function () { bar.classList.remove("show"); }, 4000);
  }

  // Mantener la pantalla encendida (Screen Wake Lock). Chrome solo lo permite en páginas
  // seguras: https, localhost o una dirección marcada como segura en chrome://flags.
  var lock = null, awake = document.getElementById("awake"), awakeWarn = document.getElementById("awake-warn");
  function showAwake(ok, why) {
    awake.textContent = ok ? "Pantalla fija" : "Puede apagarse";
    awake.style.color = ok ? "#3fb950" : "#d29922";
    awake.title = why;
    awakeWarn.style.display = ok ? "none" : "block";
  }
  function keepAwake() {
    if (!window.isSecureContext || !navigator.wakeLock) {
      showAwake(false, "Chrome no permite bloquear la pantalla en esta dirección (ver README)");
      return;
    }
    if (document.visibilityState !== "visible" || lock) { return; }
    navigator.wakeLock.request("screen").then(function (l) {
      lock = l;
      showAwake(true, "La pantalla no se apagará mientras esta página esté abierta");
      l.addEventListener("release", function () {
        lock = null;
        showAwake(false, "Se ha soltado el bloqueo; se vuelve a pedir al volver a la página");
      });
    }).catch(function (e) { showAwake(false, "No se pudo bloquear: " + e.name); });
  }
  document.addEventListener("visibilitychange", keepAwake);
  keepAwake();

  // Al tocar: pantalla completa (sin la barra de Chrome) y controles unos segundos.
  document.addEventListener("click", function () {
    keepAwake();
    if (!document.fullscreenElement && root.requestFullscreen) {
      root.requestFullscreen({ navigationUI: "hide" }).catch(function () {});
    }
    showBar();
  });

  var colors = { "true": "#3fb950", "false": "#f85149", "null": "#8b949e" };
  function esc(s) { var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
  function render(state) {
    var alertBox = document.getElementById("alert");
    alertBox.textContent = state.alert || "";
    alertBox.style.display = state.alert ? "block" : "none";

    var card = (state.cards || [])[0];
    var isNew = !card || card.id !== cardId;
    if (!card) {
      answer.className = "";
      answer.innerHTML = '<p class="hint">Listo. Pulsa una tecla para preguntar.</p>';
    } else {
      answer.className = card.error ? "error" : "";
      answer.innerHTML = card.html || '<p class="wait">Pensando…</p>';
      cardId = card.id;
    }
    if (isNew) { answer.scrollTop = 0; }
    fit(isNew);

    if (page !== null && state.page !== page) {  // F10: pasar página (al final, vuelve arriba)
      if (answer.scrollTop + answer.clientHeight >= answer.scrollHeight - 4) { answer.scrollTop = 0; }
      else { answer.scrollTop += answer.clientHeight * 0.85; }
    }
    page = state.page;

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
