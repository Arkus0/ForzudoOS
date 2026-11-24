# CapturaIA

Pulsas una tecla, la app coge el frame actual de la **capturadora**, se lo manda a **Gemini**
con una pregunta prefijada y la respuesta aparece en un **panel lateral**.

Pensada para un montaje con dos PCs:

```
PC1 ──HDMI──▶ capturadora ──USB/PCIe──▶ PC2 (CapturaIA) ──▶ API de Gemini
```

- En el PC1 no se instala nada. Para él, la capturadora es un monitor más, así que su coste es
  prácticamente cero.
- No hace falta OBS: CapturaIA lee la capturadora directamente y muestra la vista previa.
- La tecla se pulsa en un periférico del **PC2**: teclado, ratón con botones extra, macro pad o
  Stream Deck. Funciona aunque la ventana no esté en primer plano.

![Ventana de CapturaIA](docs/captura.png)

## Instalación en el PC2 (Windows)

1. **Instala uv**, que gestiona Python y las dependencias. En PowerShell:
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
2. **Descarga el código.** Con git: `git clone` del repo. También puedes bajar el ZIP desde
   GitHub. Después entra en la carpeta `capturaia`.
3. **Consigue una API key de Gemini** (gratis) en <https://aistudio.google.com/apikey> y
   guárdala como variable de entorno:
   ```powershell
   setx GEMINI_API_KEY "tu-clave"
   ```
   Cierra y vuelve a abrir la terminal para que se aplique.
4. **Arranca la app:** doble clic en `Iniciar CapturaIA.cmd`, o desde la terminal:
   ```powershell
   uv run capturaia
   ```
   La primera vez, uv descarga Python y las dependencias, así que tarda un par de minutos.

**Antes de arrancar:** si OBS u otro programa está usando la capturadora, ciérralo. La mayoría
de capturadoras solo se dejan abrir por un programa a la vez.

## Uso

| Acción | Cómo |
|---|---|
| «Explícame esto» | **F8** (o botón «Preguntar») |
| «Pon un ejemplo» | **F9** |
| «Datos clave» | **F7** |
| Entrar/salir del modo presentación | **F12** (dentro del modo, también **Esc**) |
| Pasar página en la franja de respuestas | **F10** (al final vuelve arriba) |
| Pregunta libre | Escríbela en la barra y pulsa Enter |
| Elegir capturadora | Desplegable «Fuente» (recuerda la última) |
| Dejar solo el panel | Desmarca «Vista previa» y estrecha la ventana |
| Ventana por encima de todo | «Siempre encima» |
| Ver capturas y respuestas guardadas | Archivo ▸ Abrir carpeta de capturas |
| Cambiar preguntas, teclas o modelo | Archivo ▸ Editar configuración… (y reinicia la app) |

Las respuestas aparecen mientras Gemini las escribe, con la más reciente arriba. Cada tarjeta
tiene un botón «Copiar».

Cada captura se guarda como `.jpg` junto a un `.md` con la pregunta y la respuesta. Por defecto
van a `%APPDATA%\capturaia\capturas`. Se puede desactivar en `[history]`.

Para probar sin capturadora: `uv run capturaia --demo`, que usa una imagen de prueba.
`uv run capturaia --demo foto.png` usa la imagen que le pases.

## Grabar cursos: modo presentación

Para dar un curso mirando el **monitor del PC2** mientras manejas el **portátil (PC1)** con su
propio ratón. La imagen del PC1 ocupa toda la pantalla menos una franja lateral con las
respuestas, y la franja nunca tapa la imagen.

En la grabación del PC1 no aparece nada de esto: CapturaIA vive en otro ordenador.

Monitor 21:9 (2560×1080): la imagen del PC1 a tamaño completo y la franja en el hueco sobrante.

![Modo presentación en monitor 21:9](docs/presentacion-2560x1080.png)

Monitor 16:9 (1920×1080): la imagen se reduce lo justo para dejar la franja (380 px por defecto).

![Modo presentación en monitor 16:9](docs/presentacion-1920x1080.png)

### Montaje

```
Portátil ──HDMI──▶ splitter (EDID COPY, con cargador) ──OUT1──▶ monitor
                                                      └─OUT2──▶ Cam Link 4K ──USB 3──▶ PC2 ──▶ monitor 2
```

- **La imagen va solo por cable.** El portátil manda la señal por su HDMI. El splitter la
  copia, la capturadora la convierte a USB y el PC2 la recibe. No hay red de por medio: no se
  instala nada en el portátil y el PC2 no puede leer nada de él, solo recibe la imagen.
- **Win+P ▸ «Duplicar»** (solo si usas la pantalla del portátil a la vez) hace que la pantalla
  del portátil y la salida HDMI muestren lo mismo. Va por el cable HDMI, no por wifi.
  - No confundir con «Conectar a una pantalla inalámbrica» del mismo menú: esa sí iría por wifi,
    y aquí **no se usa**.
  - Con la tapa cerrada, o usando solo el monitor externo, no hace falta tocar nada.
- **Lo único que sale a internet** es lo que el PC2 envía a Gemini cuando pulsas una tecla: la
  captura de ese momento y la pregunta. Antes de usarlo:
  - Comprueba que la política de tu organismo permite enviar a un servicio externo el
    contenido que se ve en pantalla.
  - No pulses nunca con datos personales de ciudadanos en pantalla.
  - Si no quieres guardar copias en el PC2, pon `[history] enabled = false`.
- **El PC2** no necesita estar en la red del trabajo. Basta con que tenga internet propio.

### Puesta en marcha

1. En `config.toml`, sección `[presenter]`:
   - `screen = 2` para el monitor del PC2 donde quieres verlo (1, 2, 3…).
   - `start = true` si quieres que arranque ya en este modo. También vale
     `uv run capturaia --presentar`.
2. Coloca el monitor 2 **justo detrás o debajo de la cámara** con la que te grabas. Así, al
   leer la franja, la mirada parece natural.
3. Para disparar sin soltar el ratón del PC1, conecta al PC2 un **pedal USB** o un teclado
   numérico pequeño y asígnale las teclas (F7–F10, F12, o F13–F24 si el pedal lo permite).
   Un pedal además no se oye en la grabación.

### Retraso de la imagen (importante si mueves el ratón mirando el monitor 2)

La imagen que ves en el monitor 2 lleva un pequeño retraso respecto al portátil. Para
diapositivas y señalar con el ratón suele ser cómodo, pero mídelo en tu equipo:

1. En el portátil, abre en el navegador un cronómetro con milisegundos.
2. Haz una foto con el móvil en la que salgan a la vez el monitor del splitter (OUT1) y el
   monitor 2.
3. La diferencia entre los dos números es el retraso.

Para que sea el mínimo posible:
- La barra de estado de CapturaIA (fuera del modo presentación) debe decir algo como
  `1920x1080 @ 60 fps (NV12) · recibiendo 59.9 fps`.
  - Si pone 30 fps o `Jpeg`, la Cam Link no está en un USB 3 (azul o USB-C).
- Activa el «modo juego» o de baja latencia del monitor 2 si lo tiene.
- Deja la imagen del portátil a 1920×1080 a 60 Hz. Más resolución no aporta nada a la
  capturadora y puede añadir retraso.

## Configuración

El archivo está en `%APPDATA%\capturaia\config.toml`. Se crea solo la primera vez, con todos
los valores comentados. Puedes verlo en [`config.example.toml`](config.example.toml).
Lo más habitual:

```toml
[gemini]
model = "gemini-3.8-flash"      # o "gemini-flash-latest", "gemini-3.5-flash-lite" (más rápido)
thinking_level = "low"          # minimal / low / medium / high: más alto = mejor pero más lento

[capture]
device = "HD60"                 # parte del nombre de tu capturadora (ver: uv run capturaia --list-devices)

[[presets]]
name = "Analiza"
hotkey = "<f8>"
prompt = "Describe lo que se ve en la pantalla y dime lo más importante."

[[presets]]
name = "Resumen rápido"
hotkey = "<ctrl>+<alt>+r"
prompt = "Resume en una frase lo que está pasando."
```

Puedes añadir tantos `[[presets]]` como quieras, cada uno con su tecla. Formato de teclas:

- Teclas sueltas: `<f8>`.
- Combinaciones: `<ctrl>+<alt>+g`, `<shift>+<f9>`.
- **F13–F24** no existen en un teclado normal, pero se pueden asignar en un Stream Deck o un
  macro pad. Así nunca chocan con otros programas.

## Problemas frecuentes

**No se ve imagen o sale «No encuentro…».**
- Mira los nombres con `uv run capturaia --list-devices` y pon uno en `[capture] device`.
- Comprueba que ningún otro programa (OBS, la app de la capturadora…) la tiene abierta.
- En Windows, revisa **Configuración ▸ Privacidad y seguridad ▸ Cámara ▸ Permitir que las
  aplicaciones de escritorio accedan a la cámara**. Las capturadoras cuentan como cámara.
- Si sigue fallando, prueba el modo OpenCV (DirectShow):
  ```powershell
  uv sync --extra opencv
  ```
  Después, en `config.toml`: `backend = "opencv"` y `device = "0"`. Si no es esa, prueba `"1"`,
  `"2"`… Si la imagen sale mal, prueba `fourcc = "MJPG"` o `"YUY2"`.

**La tecla no hace nada.**
- Si el programa que tiene el foco en el PC2 se ejecuta como administrador, Windows no deja que
  otras apps vean sus teclas. Arranca CapturaIA también como administrador, o usa F13–F24.
- Otro programa puede estar usando la misma tecla. Cámbiala en `[[presets]]`.
- La barra de estado de la ventana avisa si alguna tecla no es válida o está repetida.

**Errores de Gemini** (aparecen en la propia tarjeta):
- «límite de peticiones»: la cuota gratuita tiene límites por minuto y por día. Espera o cambia a
  un modelo Flash-Lite.
- «el modelo … no existe»: revisa `model` en la configuración.
- «API key no válida»: revisa `GEMINI_API_KEY`.

**Privacidad:** las capturas se envían a Google. En el nivel gratuito de la API, Google puede
usar ese contenido para mejorar sus productos; en el de pago, no. No captures pantallas con
datos sensibles.

## Desarrollo

```bash
uv sync --extra opencv
QT_QPA_PLATFORM=offscreen uv run pytest
uv run ruff check src tests && uv run ruff format --check src tests
```

Estructura:

| Archivo | Qué hace |
|---|---|
| `capture/` | Fuentes de vídeo intercambiables: `qt_source` (Qt Multimedia, por defecto), `opencv_source` (DirectShow) e `image_source` (imagen fija). |
| `gemini.py` | Manda imagen + pregunta y devuelve el texto en streaming. |
| `hotkeys.py` | Teclas globales con pynput. |
| `ui/` | Ventana principal y panel de respuestas. |
| `history.py` | Guarda capturas y respuestas en disco. |
| `config.py` | Lee y valida `config.toml`. |
