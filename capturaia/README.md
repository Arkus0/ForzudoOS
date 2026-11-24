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
| Entrar/salir del modo atril (pantalla completa) | **F12** (dentro del modo, también **Esc**) |
| Pasar página en la franja de respuestas | **F10** (al final vuelve arriba) |
| Pregunta libre | Escríbela en la barra y pulsa Enter |
| Elegir capturadora | Desplegable «Fuente» (recuerda la última) |
| Dejar solo el panel | Desmarca «Vista previa» y estrecha la ventana |
| Ventana por encima de todo | «Siempre encima» |
| Ver las respuestas en el móvil | Archivo ▸ Conectar el móvil (código QR) |
| Ver capturas y respuestas guardadas | Archivo ▸ Abrir carpeta de capturas |
| Cambiar preguntas, teclas o modelo | Archivo ▸ Editar configuración… (y reinicia la app) |

Las respuestas aparecen mientras Gemini las escribe, con la más reciente arriba. Cada tarjeta
tiene un botón «Copiar».

Cada captura se guarda como `.jpg` junto a un `.md` con la pregunta y la respuesta. Por defecto
van a `%APPDATA%\capturaia\capturas`. Se puede desactivar en `[history]`.

Para probar sin capturadora: `uv run capturaia --demo`, que usa una imagen de prueba.
`uv run capturaia --demo foto.png` usa la imagen que le pases.

## Grabar cursos: modo atril

Pensado para dar un curso grabándote sin cortes, con ayuda de Gemini, y sin que nada de eso
salga en el vídeo:

- **Trabajas en tu monitor de siempre** (la ASUS), conectado directamente al portátil: sin
  retraso, a tamaño completo, con la cámara encima. Ahí clicas, pones vídeos y presentas.
- **El monitor del PC2** (el Philips), justo al lado, enseña solo una **franja fina** con las
  respuestas, pegada al borde que toca la ASUS. El resto queda en negro. Basta un vistazo corto.
- Si el PC2, la capturadora o Gemini fallan a mitad de curso, **la grabación sigue igual**:
  solo pierdes la ayuda en ese momento.

![ASUS directa y Philips con la franja de respuestas](docs/atril.png)

### Montaje

```
Portátil ──HDMI──▶ splitter (EDID COPY, con cargador) ──OUT1──▶ ASUS (trabajas aquí, cámara encima)
                                                      └─OUT2──▶ Cam Link 4K ──USB 3──▶ PC2 ──▶ Philips (franja)
```

- **La imagen va solo por cable.** El portátil manda la señal por su HDMI y el splitter la
  copia. La capturadora la convierte a USB y el PC2 la recibe. No hay red de por medio: no se
  instala nada en el portátil y el PC2 no puede leer nada de él, solo recibe la imagen.
- **Lo que ves en la ASUS es exactamente lo que recibe la capturadora.** Si trabajas solo con
  la ASUS (tapa cerrada o sin usar la pantalla del portátil), no hay que tocar nada en Windows.
  - Win+P ▸ «Duplicar» solo haría falta si usaras a la vez la pantalla del portátil, y también
    va por cable.
  - La opción «Conectar a una pantalla inalámbrica» del mismo menú sí iría por wifi, y aquí
    **no se usa**.
- **Lo único que sale a internet** es lo que el PC2 envía a Gemini cuando pulsas una tecla: la
  captura de ese momento y la pregunta. Antes de usarlo:
  - Comprueba que la política de tu organismo permite enviar a un servicio externo el
    contenido que se ve en pantalla.
  - No pulses nunca con datos personales de ciudadanos en pantalla.
  - Si no quieres guardar copias en el PC2, pon `[history] enabled = false`.
- **El PC2** no necesita estar en la red del trabajo. Basta con que tenga internet propio.

### Puesta en marcha

1. Arranca CapturaIA en el PC2 y elige la Cam Link en «Fuente». La app la recuerda.
2. Arrastra la ventana al Philips y pulsa **F12**: pasa a pantalla completa en negro, con la
   franja a la izquierda. Si tu Philips estuviera a la izquierda de la ASUS, pon
   `side = "right"` en `[presenter]`.
3. Para arrancar siempre así, pon `start = true` en `[presenter]` o usa
   `uv run capturaia --presentar`.
4. Ajusta en `[presenter]`:
   - `strip_width`: ancho de la franja (340 px por defecto).
   - `font_size`: tamaño de letra (20 por defecto).
5. Para disparar sin soltar el ratón del portátil, conecta al PC2 un **pedal USB** o un teclado
   numérico pequeño y asígnale las teclas (F7–F10, F12, o F13–F24 si el pedal lo permite). Un
   pedal además no se oye en la grabación.
6. Las respuestas están pensadas para leerse de reojo: como mucho unas 5 viñetas cortas con la
   palabra clave en negrita. Gemini tarda unos segundos, así que ten preparada una frase puente
   («Esto es importante, fijaos bien…»).

### Antes de grabar: los tres puntos verdes

Abajo de la franja hay tres indicadores:

| Indicador | Verde | Rojo |
|---|---|---|
| **Señal** | Llega imagen de la capturadora | No llega: aviso en rojo arriba y reconexión automática cada pocos segundos |
| **Gemini** | Clave y modelo comprobados al arrancar | Falta la clave, no es válida o no hay conexión (el motivo sale arriba en rojo) |
| **Teclas** | Teclas globales activas | Alguna tecla no vale o está repetida |

**Graba solo con los tres en verde.** Si se pierde la señal, la app no envía nada a Gemini
(vería una imagen antigua) y te lo dice en la franja.

### Alternativa: ver también la imagen del portátil en el Philips

Con `show_video = true` en `[presenter]`, el Philips muestra además la imagen del portátil, con
la franja al lado. Sirve para mirar el Philips en vez de la ASUS. Ten en cuenta que:
- La imagen sale algo más pequeña en un monitor 16:9 y con un pequeño retraso.
- Dependes de que el PC2 no falle.

Para cursos en los que tienes que clicar con precisión, es mejor el modo atril.

<details><summary>Cómo queda con imagen (16:9 y 21:9)</summary>

![Con imagen en monitor 21:9](docs/presentacion-2560x1080.png)
![Con imagen en monitor 16:9](docs/presentacion-1920x1080.png)

</details>

## Respuestas en el móvil (sin segundo monitor)

En vez del segundo monitor, puedes leer las respuestas en el **móvil**, puesto con un cuello de
cisne pegado a tu monitor, casi en la línea de la cámara. El PC2 se queda debajo de la mesa,
sin pantalla.

<img src="docs/movil.png" alt="Respuestas en el móvil" width="300">

```
Portátil ──HDMI──▶ splitter ──OUT1──▶ ASUS (trabajas aquí, cámara encima, móvil al lado)
                            └─OUT2──▶ Cam Link ──USB──▶ PC2 (sin monitor) ──wifi de casa──▶ móvil
```

- **Sin apps ni cuentas:** el móvil abre una página que sirve el propio PC2 en tu wifi de casa.
  Las respuestas no pasan por ningún servidor de fuera. La dirección lleva una clave aleatoria
  para que otro aparato de la red no pueda leerla.
- **Se actualiza sola** mientras Gemini escribe. La última respuesta sale arriba en grande y las
  anteriores, atenuadas debajo.
- **Fondo negro puro y texto gris suave.** Con los botones de abajo cambias el tamaño de letra
  (A−/A+) y el brillo del texto (☀−/☀+); el móvil lo recuerda.
- **Si se corta,** el móvil muestra «Sin conexión con CapturaIA» en rojo, y en el PC2 el
  indicador **Móvil** se pone en rojo.

### Primera vez

1. En el PC2, abre **Archivo ▸ Conectar el móvil**: sale un código QR y la dirección
   (`http://IP-del-PC2:8765/…/`).
   - Para ver el PC2 en esta configuración inicial, conéctalo un momento a la otra entrada de
     la ASUS (HDMI o DisplayPort) y luego vuelve a la del portátil.
2. Escanéalo con la cámara del móvil. En Chrome: menú ⋮ ▸ **Añadir a pantalla de inicio**, y
   la próxima vez la abres con un toque. La dirección no cambia.
3. Si Windows pregunta si deja a Python acceder a la red, acepta **solo para redes privadas**.
4. Para que CapturaIA arranque sola con el PC2: Win+R ▸ `shell:startup` y deja ahí un acceso
   directo a `Iniciar CapturaIA.cmd`.

### Que la pantalla del móvil no se apague (Pixel 7 / Android)

1. Deja el móvil **cargando** mientras grabas (el cable va por el cuello de cisne).
2. Activa las Opciones para desarrolladores: Ajustes ▸ Información del teléfono ▸ pulsa 7 veces
   en «Número de compilación».
3. En Ajustes ▸ Sistema ▸ Opciones para desarrolladores, activa **«Pantalla activa»**: la
   pantalla no se apaga mientras carga.
4. Baja el brillo del móvil. Con fondo negro, el Pixel apenas emite luz y no te ilumina la cara.

En iPhone: Ajustes ▸ Pantalla y brillo ▸ Bloqueo automático ▸ Nunca.

### Lanzar las preguntas sin tocar nada visible

Empareja con el **PC2** (no con el móvil) un mando pequeño con modo teclado, como algunos
8BitDo (Micro, Zero 2…; comprueba que el modelo tenga «keyboard mode»), o un pedal USB. Con su
programa, asigna a los botones F8, F9, F7, F10 (pasar página) y F12. CapturaIA ya los entiende
como teclas globales.

### ¿Y quitar también el PC2, con la capturadora enchufada al móvil?

El móvil puede **ver** la capturadora con una app de cámara USB, pero eso solo muestra la
pantalla del portátil en el móvil: **no genera respuestas**. Hacerlo todo en el móvil
(capturar, preguntar a Gemini y mostrar) exigiría una app de Android hecha a medida.
Además:
- Con la capturadora en el único USB-C, haría falta un adaptador con carga para que no se
  quede sin batería.
- El móvil se calentaría en sesiones largas.

Para grabaciones que tienen que salir bien a la primera, el PC2 sin monitor es más fiable: hace
el trabajo pesado enchufado a la corriente, y el móvil solo muestra texto.

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
