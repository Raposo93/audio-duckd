# Desarrollo y validación

## Preparación

Python >= 3.10 y Git son necesarios para la validación local. Crear `.venv` e
instalar `requirements.txt` para ejecutar el daemon, siguiendo el
[README](../README.md#arranque-manual). Las pruebas con backend simulado no
requieren `pulsectl`, libpulse ni servidor de audio. Instalar las dependencias de
desarrollo antes de validar:

```sh
.venv/bin/python -m pip install -r requirements-dev.txt
```

En un entorno creado con uv sin pip, usar:

```sh
uv pip install --python .venv/bin/python -r requirements-dev.txt
```

Pytest es el ejecutor oficial; descubre también las clases `unittest.TestCase`
existentes. No es necesario reescribirlas para ejecutar la suite con pytest.

## Arquitectura

| Módulo | Responsabilidad |
| --- | --- |
| `audio_duckd/__main__.py` | Argumentos, configuración, señales, sondeo y cierre. |
| `audio_duckd/config.py` | Configuración y validación sin acceso al audio. |
| `audio_duckd/backend.py` | Adaptador de libpulse, representación de streams y guardas de escritura. |
| `audio_duckd/detection.py` | Identificación de actividad y objetivos a partir de streams. |
| `audio_duckd/policy.py` | Guardado, atenuación proporcional, restauración y reintentos. |
| `tests/` | Contratos y comportamiento con adaptadores simulados. |

Los lanzadores de compatibilidad delegan en el módulo; no deben incorporar otra
implementación de la política. Mantener las decisiones de dominio independientes
de `pulsectl`.

## Validación local completa

Desde cualquier directorio:

```sh
/ruta/al/repositorio/check.sh
```

Desde la raíz basta con `./check.sh`. El script selecciona `.venv/bin/python`
cuando está disponible y usa `python3` en caso contrario. Comprueba Python >= 3.10,
diffs de trabajo y preparados para commit, marcadores de conflicto en archivos
versionados y sintaxis del lanzador shell y del propio script; después ejecuta
la suite completa con pytest. Los archivos nuevos quedan cubiertos por las
pruebas cuando pertenecen a los módulos o tests descubiertos; revisar además su
diff y contenido antes de incorporarlos a Git.

No instala dependencias, conecta al servidor de audio, modifica servicios ni
inicia el daemon. No incluye todavía lint, formato ni comprobación estática de
tipos: incorporarlos cuando se declaren sus configuraciones y dependencias.
CI debe reutilizar `./check.sh` cuando se añada un workflow.

## Pruebas automáticas

Con las dependencias de desarrollo instaladas, sin servidor de audio:

```sh
.venv/bin/python -m pytest tests -v
```

Cubren entrada/salida de actividad, silencio/mute/corked, varios streams,
reproducción/captura, cambios de volumen, desaparición/reutilización de índices,
reintentos, exclusión de Linphone/Discord, configuración predeterminada,
límites, selectores contradictorios y validación antes de conectar al backend. El adaptador se prueba con una API
simulada; no sustituye una prueba de integración con un servidor real.

## Criterio de validación

Ejecutar las pruebas pertinentes durante el desarrollo y `./check.sh` antes de
solicitar revisión. Añadir pruebas para cambios de comportamiento y fallos
relevantes; no crear pruebas de documentación o detalles internos por rutina.

Las comprobaciones reales se mantienen separadas en [operations.md](operations.md).
Una suite verde no demuestra el ciclo de vida real de Linphone ni la restauración
ante una caída de servidor. Conservar explícitos los criterios pendientes.
