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

Los errores de configuración terminan con código 2; los fallos de conexión o
enumeración terminan con código 1. Los fallos de escritura se registran y se
reintentan durante el sondeo. Consultar las garantías y límites de restauración
en [behavior.md](behavior.md). Si la restauración falla o el proceso termina
abrutamente, comprobar y ajustar manualmente el volumen de los objetivos.

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

Si una etapa falla, guardar JSON antes/después, versiones y logs del daemon.
**El ciclo de vida real de Linphone sigue sin verificar** hasta completar estas
pruebas; no se debe dar por cerrado ese criterio solo con el backend simulado.

## Registro de resultados

Registrar fecha con zona horaria, commit y cambios locales, versiones, configuración
efectiva, etapas ejecutadas y resultados observados. Conservar los JSON y logs
localmente; revisar su contenido antes de compartirlos y no versionar registros
de una sesión de usuario. Distinguir resultados correctos, fallidos y no ejecutados.
No ejecutar llamadas ni cambiar servicios como parte de la validación local.
