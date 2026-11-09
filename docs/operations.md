# Operación y comprobación real

## Ejecución

Ejecutar desde el repositorio siguiendo el [arranque manual](../README.md#arranque-manual).
Para usar otra configuración, pasar `--config RUTA`; su contrato está en
[configuration.md](configuration.md).

`linphone-duck.sh` se conserva como lanzador de compatibilidad, sin lógica de audio;
requiere tener el módulo y `linphone-duck.py` junto a él, y el intérprete con las
dependencias en `PATH` (o en `PYTHON`). El servicio `linphone-duck.service` es el
legado: la instalación definitiva con systemd corresponde a otro issue. Para
probar manualmente, detener cualquier instancia anterior, incluido ese servicio
si está instalado (`systemctl --user stop linphone-duck.service`), y no ejecutar
dos instancias simultáneas.

## Diagnóstico y recuperación

`--inspect` enumera streams sin escribir volumen ni mute. No arrancar una segunda
instancia del daemon para diagnosticar: utilizar ese modo de inspección.

Los errores de configuración terminan con código 2. El daemon reintenta conexiones
fallidas; `--inspect` termina con código 1 ante fallos de conexión o enumeración.
Un fallo de enumeración con conexión activa termina el daemon con código 1. Los
fallos de escritura de un stream se registran y se reintentan durante el sondeo.
Consultar el [contrato de reconexión](behavior.md#reconexión) y las garantías de restauración
en [behavior.md](behavior.md#parada-del-daemon). Una parada con originales pendientes
o un fallo al cerrar el backend también termina con código 1. Buscar en los logs
`Could not restore` y `Unrestored target identities` para identificar los streams
afectados. Si la restauración falla o el proceso termina
abrutamente, comprobar y ajustar manualmente el volumen de los objetivos.

`Audio server unavailable` indica un intento de reconexión, y
`starting a new stream session` indica que se ha creado una conexión nueva. Si se
registra `Volume writes suspended after disconnect`, el daemon sigue enumerando
pero no escribe volúmenes hasta reiniciarlo. Ni terminar la llamada ni otra
reconexión eliminan esa suspensión. Comprobar y corregir manualmente los volúmenes
de todos los objetivos antes de reiniciar el daemon: el servidor o la aplicación
pueden haber conservado el volumen reducido. No aplicar el factor inverso de forma
automática. La suspensión implica salida con código 1 al detenerlo, aunque la
conexión ya se haya recuperado.

## Comprobación real de reconexión

Pendiente de ejecutar en la sesión de usuario con `pipewire-pulse`. Esta prueba
interrumpe el audio y queda fuera de `./check.sh`. Registrar versiones, configuración,
commit, volúmenes por canal y logs según el registro de resultados de este documento.

1. Con Linphone sin streams y Brave reproduciendo, iniciar una sola instancia del
   daemon y guardar `--inspect`.
2. Reiniciar manualmente `pipewire-pulse` con
   `systemctl --user restart pipewire-pulse.service`; comprobar la espera entre
   intentos y la conexión nueva sin reiniciar el daemon.
3. Guardar otra inspección: los índices pueden reutilizarse. Iniciar la llamada de
   prueba y comprobar que cada objetivo usa sus volúmenes de la sesión nueva,
   conserva el balance y restaura esos valores al terminar la llamada.
4. Repetir la interrupción durante ducking. Comprobar el mensaje de suspensión y
   las identidades pendientes, la reconexión y la ausencia de nuevas escrituras,
   tanto durante la llamada como después de terminarla o abrir otro objetivo.
   Detener el daemon (código 1), comprobar/corregir manualmente los volúmenes y
   reiniciarlo; verificar una nueva atenuación y restauración sobre esa base.
5. Comprobar por separado Ctrl+C y SIGTERM durante los reintentos, sin que se inicie
   otro intento tras la petición de parada. Confirmar que Linphone y Discord
   conservan sus volúmenes y mute en todas las etapas.

Registrar resultados correctos, fallidos y no ejecutados. Las pruebas simuladas no
establecen si las aplicaciones conservan sus volúmenes tras el reinicio real.

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
| Llamada entrante/saliente, timbre y conexión | Registrar cuándo aparecen los streams y cuándo Brave pasa al volumen original × 0,2. |
| Llamada en silencio durante 10 s | Los streams deben persistir y Brave seguir atenuado. |
| Micrófono silenciado y reactivado desde Linphone | Registrar si persisten captura o reproducción; Brave debe seguir atenuado. |
| Micrófono silenciado desde el sistema | Repetir la comprobación; no se debe escribir ningún mute. |
| Nueva reproducción/pestaña de Brave durante llamada | Su stream también debe multiplicar su volumen por 0,2. |
| Discord abierto durante la prueba | Su volumen y mute deben conservarse, igual que los de Linphone. |
| Cambiar manualmente Brave durante llamada | En aproximadamente 0,5 s debe volver al original × 0,2. |
| Colgar, tanto local como remotamente | Registrar cuándo desaparece el último stream de Linphone y confirmar la restauración por canal. |
| Ctrl+C o SIGTERM durante llamada | Brave debe restaurarse y Linphone/Discord conservar volumen y mute. |

Repetir la etapa de parada por separado con Ctrl+C y SIGTERM, reiniciando el daemon
y anotando de nuevo los originales antes de cada prueba. Comprobar el código de
salida, la restauración de todos los streams supervivientes y el cierre del proceso;
incluir un objetivo que desaparezca antes de la parada. Esta aceptación real sigue
pendiente; las pruebas automáticas solo validan el flujo con un backend simulado.

Si una etapa falla, guardar JSON antes/después, versiones y logs del daemon.
**El ciclo de vida real de Linphone sigue sin verificar** hasta completar estas
pruebas; no se debe dar por cerrado ese criterio solo con el backend simulado.

## Registro de resultados

Registrar fecha con zona horaria, commit y cambios locales, versiones, configuración
efectiva, etapas ejecutadas y resultados observados. Conservar los JSON y logs
localmente; revisar su contenido antes de compartirlos y no versionar registros
de una sesión de usuario. Distinguir resultados correctos, fallidos y no ejecutados.
No ejecutar llamadas ni cambiar servicios como parte de la validación local.
