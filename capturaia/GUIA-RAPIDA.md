# Guía rápida de CapturaIA

Tu montaje, sin alternativas: trabajas en la ASUS como siempre y lees las respuestas de Gemini en
el móvil, sin cable.

## Cómo funciona

```
Portátil del trabajo ──HDMI──▶ splitter ──▶ ASUS (aquí trabajas y te graba la cámara)
                                       └──▶ capturadora ──USB──▶ PC2 (debajo de la mesa)
PC2 ──(F8)──▶ Gemini ──respuesta──▶ PC2 ──depuración inalámbrica──▶ móvil junto a la ASUS
```

1. El portátil manda la imagen a la ASUS y el splitter manda una copia a la capturadora.
   **El portátil no se entera de nada** y no se le instala nada.
2. El PC2 recibe esa imagen todo el rato, pero no hace nada con ella.
3. Pulsas **F8** en el mando: el PC2 coge la imagen de ese momento y se la manda a Gemini con
   tu pregunta.
4. Gemini responde en unos segundos.
5. La respuesta aparece en el móvil.

Todo eso lo hace CapturaIA sola. Tú solo pulsas el botón y lees.

---

## Una sola vez (en este orden)

**En el PC2**

1. Instala **uv** (abre PowerShell y pega):
   `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
2. Descarga CapturaIA (el ZIP del repositorio en GitHub) y entra en la carpeta `capturaia`.
3. Guarda tu clave de Gemini (gratis en <https://aistudio.google.com/apikey>). En PowerShell:
   `setx GEMINI_API_KEY "tu-clave"`, y cierra PowerShell.
4. Descarga **«SDK Platform-Tools for Windows»** de
   <https://developer.android.com/tools/releases/platform-tools> y descomprímelo **dentro de la
   carpeta `capturaia`**. Tiene que quedar `capturaia\platform-tools\adb.exe`.
5. Conecta el PC2 a la **segunda entrada de la ASUS** (HDMI o DisplayPort) y déjalo así.
   - Cuando quieras ver el PC2, cambia la entrada de la ASUS; luego vuelve a la del portátil.
   - Si la ASUS solo tiene una entrada, usa un adaptador «HDMI dummy» en el PC2.
6. Doble clic en **`Iniciar CapturaIA.cmd`**. La primera vez tarda un par de minutos.
7. En la ventana, elige la capturadora (Cam Link) en **«Fuente»**. Se queda guardada.
8. Para que arranque sola con el PC2: pulsa Win+R, escribe `shell:startup` y deja ahí un
   acceso directo a `Iniciar CapturaIA.cmd`.

**En el móvil (Pixel)**

9. Ajustes ▸ Información del teléfono ▸ pulsa **7 veces** en «Número de compilación» (activa
   las Opciones para desarrolladores).
10. Ajustes ▸ Sistema ▸ Opciones para desarrolladores ▸ **Depuración inalámbrica** ▸ actívala.
    - Truco: en esas mismas opciones, busca «Iconos para desarrolladores en ajustes rápidos» y
      añade «Depuración inalámbrica». Así la activas desde la cortina de notificaciones.
11. Emparéjalos:
    - En el PC2: **Archivo ▸ Emparejar el móvil sin cable**.
    - En el móvil: Depuración inalámbrica ▸ «Vincular dispositivo con código de vinculación».
    - Escribe en el PC2 la IP:puerto y el código de 6 cifras, y pulsa «Emparejar».
12. Abre la página en el móvil:
    - En el PC2: **Archivo ▸ Conectar el móvil**.
    - Escanea el código QR con el móvil (la dirección empieza por `http://localhost:8765/`).
    - En Chrome: ⋮ ▸ **Añadir a pantalla de inicio**. Ya tienes un icono para abrirla.

**El mando (8BitDo o similar)**

13. Ponlo en **modo teclado** y empareja por Bluetooth con el **PC2** (no con el móvil).
    Con su programa, asigna a los botones:
    - **F8**: Explícame esto
    - **F9**: Pon un ejemplo
    - **F7**: Datos clave
    - **F10**: pasar página si la respuesta es larga

---

## Cada día de grabación

- [ ] Enciende el PC2 (CapturaIA arranca sola).
- [ ] Móvil en la wifi de casa, con el **cargador** puesto.
- [ ] Activa **Depuración inalámbrica** (Android la apaga al reiniciar o cambiar de wifi).
- [ ] Abre el icono de CapturaIA, pon el móvil **en horizontal** y **toca la pantalla una vez**.
      Pasa a pantalla completa y ya no se apaga.
- [ ] Comprueba que pone **«Listo. Pulsa una tecla para preguntar.»**, sin avisos en rojo ni
      la nota amarilla «La pantalla puede apagarse».
- [ ] Haz un **F8 de prueba** con la primera diapositiva y mira que llega la respuesta.
- [ ] A grabar. Gemini tarda unos segundos, así que ten una frase puente preparada («Esto es
      importante, fijaos bien…»).

---

## Si algo falla

**Si falla algo mientras grabas, sigue dando el curso.** La grabación del portátil no se ve
afectada; solo pierdes la ayuda en ese momento.

| Lo que ves en el móvil | Qué hacer |
|---|---|
| «Sin conexión con CapturaIA» (rojo) | Comprueba que el PC2 está encendido y que **Depuración inalámbrica** sigue activada; reactívala si se apagó. Se reconecta sola en unos segundos. |
| «Sin señal de la capturadora» | Revisa el cable HDMI que va del splitter a la capturadora y el USB de la capturadora al PC2. Se reconecta sola. |
| «Gemini no está listo: …» | La clave de Gemini falta o no es válida, o el PC2 no tiene internet. Revisa el paso 3. |
| «Teclas: …» | El PC2 no ha podido activar las teclas. Cierra CapturaIA y vuelve a abrirla con `Iniciar CapturaIA.cmd`. |
| «La pantalla puede apagarse» (amarillo, abajo) | Toca la pantalla una vez. Si sigue, cierra y abre la página desde el icono: tiene que ser la dirección `localhost`. |
| Pulsas el mando y no pasa nada (sin ningún aviso) | Mira que el mando esté encendido y emparejado con el **PC2**, y que sus botones envíen F8/F9/F7. Para comprobarlo, pulsa F8 en un teclado conectado al PC2. |
| La respuesta no cabe | Pulsa **F10** para pasar página. |

---

## Recuerda

- Solo sale a internet la imagen del momento en que pulsas, y va del PC2 a Gemini.
  **No pulses nunca con datos personales de ciudadanos en pantalla.**
- Revisa que tu organismo permite enviar el contenido de los cursos a un servicio externo.
- La referencia completa (todas las opciones) está en el [README](README.md).
