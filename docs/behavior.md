# Comportamiento y límites

- El bucle sondea cada
  0,5 segundos, sin callbacks que escriban dentro del bucle de eventos de libpulse.
- Se compara `application.process.binary` con los selectores configurados,
  retirando únicamente el sufijo ` (deleted)`. Si la distribución usa
  otro nombre, se debe comprobar con `--inspect` antes de adaptar la detección.
- La presencia de **reproducción o captura** de Linphone aproxima el estado de
  llamada. Silencio, mute y `corked` no desactivan el ducking si persiste el stream.
  También pueden activarlo un timbre o una prueba de audio. No es detección SIP.
  Si Linphone mantiene streams en reposo, o elimina todos al silenciar, esta
  aproximación no cumple el ciclo esperado: debe verificarse en el equipo real.
- Cada stream objetivo nuevo se atenúa aunque aparezca durante la llamada. Los
  cambios manuales durante ella vuelven al original multiplicado por el factor
  en el siguiente sondeo; al salir se recupera el volumen anterior a la llamada.
  El original se guarda una sola vez: los sondeos no acumulan la atenuación. Se
  conserva el balance por canal durante la atenuación y al restaurar.
- Se descartan volúmenes de streams desaparecidos. No se transfiere un volumen
  guardado a un stream nuevo. La identidad incluye dirección, índice, cliente,
  PID y binario; antes de escribir se vuelve a comprobar. La API no proporciona
  una escritura condicional atómica frente a desapariciones concurrentes.
- Si cambia el número de canales de un objetivo con original guardado, no se
  escribe ni atenuación ni restauración hasta que vuelva a coincidir. Se conserva
  el original para reintentar; si el stream desaparece, se descarta. No se adapta
  un volumen guardado a otro número de canales. El mute actual se conserva,
  incluidos los cambios manuales durante el ducking.
- Los fallos de escritura se registran y reintentan en el siguiente sondeo. Un
  fallo al enumerar/conectar termina con código 1 e intenta restaurar. No hay
  reconexión automática ni persistencia: SIGKILL, caída del servidor o del proceso
  pueden impedir restaurar el volumen. Comprobar Brave manualmente en esos casos.

## Parada del daemon

SIGINT (Ctrl+C) y SIGTERM solicitan detener el sondeo y despiertan su espera.
La operación síncrona de audio en curso debe regresar antes de iniciar la limpieza;
no hay tareas en segundo plano ni monitores de audio en esta versión. Se realiza
una pasada de restauración de los originales guardados, incluso si Linphone sigue
presente, antes de cerrar la conexión al backend. Las señales repetidas mantienen
la petición de parada sin interrumpir esa limpieza.

Solo se restauran identidades y números de canales que sigan coincidiendo. Un
stream desaparecido se descarta; un fallo al escribir un stream no impide intentar
los demás. Una restauración correcta elimina su original guardado, por lo que
repetir la restauración no vuelve a escribirlo. Si falla la enumeración, se conservan
los originales en memoria pero no se escribe a partir de información antigua.

La salida es 0 cuando la ejecución y la limpieza terminan correctamente, o 1 ante
errores del backend, cierre fallido u originales que no pudieron restaurarse. Los
logs distinguen atenuación y restauración e incluyen la identidad del stream;
al salir se enumeran las identidades pendientes. No hay reintentos adicionales de
restauración al salir ni persistencia tras terminar el proceso. SIGKILL, una caída
del proceso o un servidor inaccesible pueden impedir la limpieza: no se garantiza
la recuperación en esos casos. Ver [diagnóstico y recuperación](operations.md#diagnóstico-y-recuperación).

## Dependencia y compatibilidad

Se fija **pulsectl==24.12.0**, una interfaz síncrona de `libpulse` con listas de
streams, propiedades y volúmenes por canal estructurados. No se analiza texto
localizado ni se ejecutan comandos de `pactl`.

La [documentación de pulsectl](https://pypi.org/project/pulsectl/24.12.0/) describe
esas operaciones de introspección y escritura de volumen mediante `libpulse`.
La [documentación de pipewire-pulse](https://pipewire.pages.freedesktop.org/pipewire/page_man_pipewire-pulse_1.html)
lo define como sustituto compatible de PulseAudio. Esa combinación fundamenta la
compatibilidad de API; no equivale a una prueba de una llamada real en este entorno.

Los parámetros y sus validaciones se definen en [configuration.md](configuration.md).
La comprobación de integración se describe en [operations.md](operations.md).
