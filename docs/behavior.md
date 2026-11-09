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
- Los fallos de escritura de un stream se registran y reintentan en el siguiente
  sondeo. Una desconexión se trata aparte según el contrato de reconexión siguiente.
  Un fallo al enumerar mientras la conexión sigue activa termina con código 1 e
  intenta restaurar. No hay persistencia: SIGKILL, caída del servidor o del proceso
  pueden impedir restaurar el volumen. Comprobar Brave manualmente en esos casos.

## Reconexión

Cada intento de conexión usa un timeout de 2 segundos y no inicia un servidor de
audio automáticamente. Si el servidor no está disponible al arrancar, o se pierde
la conexión, se cierra el backend anterior y se reintenta con esperas de 0,5, 1, 2,
4 y hasta 5 segundos entre intentos, sin límite de intentos. SIGINT y SIGTERM
interrumpen esa espera; la conexión síncrona en curso debe regresar primero.
Una enumeración completa correcta reinicia la espera a 0,5 segundos. `--inspect`
sigue siendo una consulta única: termina con código 1 ante fallos de conexión o
enumeración, sin reconectar ni modificar audio.

Una conexión nueva crea un backend y una política nuevos, sin identidades ni
originales de la sesión anterior. Se enumeran de nuevo reproducción y captura y se
recalcula la actividad de Linphone. Se mantiene el sondeo: no hay suscripciones ni
monitores de Discord en esta versión.

Si la conexión se pierde con originales guardados, el daemon **suspende todas las
escrituras de volumen hasta su reinicio**, aunque termine la llamada, aparezcan
otros streams o se reconecte otra vez. Sigue reconectando y enumerando en modo de
solo lectura. Registra las identidades que no pudieron restaurarse y la necesidad
de comprobar manualmente los volúmenes antes de reiniciar; al parar termina con
código 1. Si no había originales en riesgo, se reanuda el ducking automáticamente
con los volúmenes de la sesión nueva y la parada normal puede terminar con código 0.

También se considera en riesgo un original cuando la conexión falla durante su
escritura, porque el servidor podría haberla aplicado antes de perder la confirmación.
No se reutilizan originales de otra conexión, ni se toma un volumen posiblemente
atenuado como nueva base. Tampoco se intenta invertir el factor: podría aumentar
el volumen de un stream distinto y no funciona con factor cero. Esta suspensión
evita que un volumen retenido por el servidor se atenúe repetidamente; no recupera
por sí misma los volúmenes anteriores.

## Parada del daemon

SIGINT (Ctrl+C) y SIGTERM solicitan detener el sondeo y despiertan su espera.
La operación síncrona de audio en curso debe regresar antes de iniciar la limpieza;
no hay tareas en segundo plano ni monitores de audio en esta versión. Se realiza
una pasada de restauración de los originales guardados, incluso si Linphone sigue
presente, antes de cerrar la conexión al backend. Las señales repetidas mantienen
la petición de parada sin interrumpir esa limpieza.

Solo se restauran identidades y números de canales de la conexión actual que sigan
coincidiendo, si las escrituras no están suspendidas. Un
stream desaparecido se descarta; un fallo al escribir un stream no impide intentar
los demás. Una restauración correcta elimina su original guardado, por lo que
repetir la restauración no vuelve a escribirlo. Si falla la enumeración durante la
limpieza de la conexión actual, se conservan
los originales en memoria pero no se escribe a partir de información antigua.

La salida es 0 cuando la ejecución y la limpieza terminan correctamente, o 1 ante
errores definitivos del backend, cierre fallido, suspensión de escrituras u originales
que no pudieron restaurarse. Una desconexión recuperada sin volúmenes en riesgo no
implica por sí sola una salida con código 1. Los
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
