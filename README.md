# audio-duckd

Daemon Python para bajar los streams de reproducción de Brave al **20 % absoluto**
mientras exista algún stream de Linphone. Al desaparecer el último, restaura el
volumen original de cada canal de cada stream. No escribe volumen ni mute de
Linphone o Discord, ni modifica el mute de Brave.

## Arranque manual

Requisitos: Linux, Python >= 3.10, `libpulse.so.0` (habitualmente paquete
`libpulse0`) y un servidor PulseAudio o `pipewire-pulse` en la sesión del usuario.
No se necesita `pactl`. Ejecutar desde este repositorio, sin sudo:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m audio_duckd
```

En Debian/Ubuntu puede ser necesario instalar `python3-venv` para crear el entorno.
También se puede usar `uv venv` seguido de `uv pip install -r requirements.txt`.
Alternativa de ejecución: `.venv/bin/python linphone-duck.py`.
Ctrl+C y SIGTERM intentan restaurar Brave antes de salir.

`linphone-duck.sh` se conserva como lanzador de compatibilidad, sin lógica de audio;
requiere tener el módulo y `linphone-duck.py` junto a él, y el intérprete con las
dependencias en `PATH` (o en `PYTHON`). El servicio `linphone-duck.service` es el
legado: la instalación definitiva con systemd corresponde a otro issue. Para
probar manualmente, detener cualquier instancia anterior, incluido ese servicio
si está instalado (`systemctl --user stop linphone-duck.service`), y no ejecutar
dos instancias simultáneas.

## Dependencia y compatibilidad

Se fija **pulsectl==24.12.0**, una interfaz síncrona de `libpulse` con listas de
streams, propiedades y volúmenes por canal estructurados. No se analiza texto
localizado ni se ejecutan comandos de `pactl`.

La [documentación de pulsectl](https://pypi.org/project/pulsectl/24.12.0/) describe
esas operaciones de introspección y escritura de volumen mediante `libpulse`.
La [documentación de pipewire-pulse](https://pipewire.pages.freedesktop.org/pipewire/page_man_pipewire-pulse_1.html)
lo define como sustituto compatible de PulseAudio. Esa combinación fundamenta la
compatibilidad de API; no equivale a una prueba de una llamada real en este entorno.

## Comportamiento y límites

- `backend.py` encapsula `pulsectl`; `detection.py` decide la actividad y los
  destinos; `policy.py` guarda, aplica y restaura volúmenes. El bucle sondea cada
  0,5 segundos, sin callbacks que escriban dentro del bucle de eventos de libpulse.
- Se identifica `application.process.binary` exactamente como `linphone` o
  `brave`, retirando únicamente el sufijo ` (deleted)`. Si la distribución usa
  otro nombre, se debe comprobar con `--inspect` antes de adaptar la detección.
- La presencia de **reproducción o captura** de Linphone aproxima el estado de
  llamada. Silencio, mute y `corked` no desactivan el ducking si persiste el stream.
  También pueden activarlo un timbre o una prueba de audio. No es detección SIP.
  Si Linphone mantiene streams en reposo, o elimina todos al silenciar, esta
  aproximación no cumple el ciclo esperado: debe verificarse en el equipo real.
- Cada stream nuevo de Brave se baja aunque aparezca durante la llamada. Los
  cambios manuales durante ella vuelven al 20 % en el siguiente sondeo; al salir
  se recupera el volumen anterior a la llamada. Se conserva el balance original
  al restaurar. El 20 % es absoluto, igual que en el script anterior, incluso si
  el volumen previo era inferior.
- Se descartan volúmenes de streams desaparecidos. No se transfiere un volumen
  guardado a un stream nuevo. La identidad incluye dirección, índice, cliente,
  PID y binario; antes de escribir se vuelve a comprobar. La API no proporciona
  una escritura condicional atómica frente a desapariciones concurrentes.
- Los fallos de escritura se registran y reintentan en el siguiente sondeo. Un
  fallo al enumerar/conectar termina con código 1 e intenta restaurar. No hay
  reconexión automática ni persistencia: SIGKILL, caída del servidor o del proceso
  pueden impedir restaurar el volumen. Comprobar Brave manualmente en esos casos.

## Pruebas automáticas

Sin servidor de audio ni dependencia instalada:

```sh
python3 -m unittest discover -s tests -v
```

Cubren entrada/salida de actividad, silencio/mute/corked, varios streams,
reproducción/captura, cambios de volumen, desaparición/reutilización de índices,
reintentos y exclusión de Linphone/Discord. El adaptador se prueba con una API
simulada; no sustituye una prueba de integración con un servidor real.

## Comprobación real de Linphone y pipewire-pulse

Pendiente de realizar en una sesión con ambas aplicaciones. Registrar versiones
de Linphone, PipeWire y Python, y confirmar que se usa `pipewire-pulse` (por
ejemplo `systemctl --user status pipewire-pulse.service`). Usar una llamada de
prueba y guardar la salida JSON de este comando en cada etapa:

```sh
.venv/bin/python -m audio_duckd --inspect
```

`--inspect` es de solo lectura y muestra identidad, dirección, volúmenes, mute y
`corked`. Se puede ejecutar en otra terminal mientras corre el daemon.

| Etapa | Qué comprobar |
| --- | --- |
| Linphone abierto sin llamada | No debe haber streams de Linphone si se quiere aproximar llamada con esta política. |
| Brave reproduciendo, antes de llamar | Anotar índice y volumen de cada canal, incluido uno con balance desigual. |
| Llamada entrante/saliente, timbre y conexión | Registrar cuándo aparecen los streams y cuándo Brave pasa al 20 %. |
| Llamada en silencio durante 10 s | Los streams deben persistir y Brave seguir al 20 %. |
| Micrófono silenciado y reactivado desde Linphone | Registrar si persisten captura o reproducción; Brave debe seguir al 20 %. |
| Micrófono silenciado desde el sistema | Repetir la comprobación; no se debe escribir ningún mute. |
| Nueva reproducción/pestaña de Brave durante llamada | Su stream también debe bajar al 20 %. |
| Discord abierto durante la prueba | Su volumen y mute deben conservarse, igual que los de Linphone. |
| Cambiar manualmente Brave durante llamada | En aproximadamente 0,5 s debe volver al 20 %. |
| Colgar, tanto local como remotamente | Registrar cuándo desaparece el último stream de Linphone y confirmar la restauración por canal. |
| Ctrl+C o SIGTERM durante llamada | Brave debe restaurarse y Linphone/Discord conservar volumen y mute. |

Si una etapa falla, guardar JSON antes/después, versiones y logs del daemon.
**El ciclo de vida real de Linphone sigue sin verificar** hasta completar estas
pruebas; no se debe dar por cerrado ese criterio solo con el backend simulado.
