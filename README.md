# audio-duckd

Daemon Python para atenuar los streams de reproducción de las aplicaciones objetivo
(Brave por defecto) mientras exista algún stream de Linphone. Aplica un
**factor proporcional de 0,2** por defecto: un volumen del 10 % pasa al 2 %. Al desaparecer el último, restaura el
volumen original de cada canal de cada stream. No escribe volumen ni mute de
las aplicaciones seleccionadas como Linphone o Discord, ni modifica ningún mute.

**Estado:** el ciclo de vida real de Linphone sigue pendiente de verificación.
Discord está excluido de los objetivos, pero todavía no activa la atenuación ni
se mide su señal. Sus parámetros de señal solo definen un contrato futuro.

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
Si se pierde la conexión al servidor de audio, consultar la
[reconexión y suspensión de escrituras](docs/behavior.md#reconexión) antes de reiniciar
el daemon: puede ser necesario corregir manualmente los volúmenes.

## Configuración

Para personalizar los valores, copiar [config.example.json](config.example.json)
y pasar su ruta explícitamente:

```sh
.venv/bin/python -m audio_duckd --config config.example.json
```

No se busca configuración automáticamente ni se recarga durante la ejecución.
Consultar el [contrato de configuración](docs/configuration.md).

## Inspección y validación

Inspección de solo lectura, con las dependencias de ejecución instaladas:

```sh
.venv/bin/python -m audio_duckd --inspect
```

Comprobación local sin servidor de audio, tras instalar las
[dependencias de desarrollo](docs/development.md#preparación):

```sh
./check.sh
```

## Documentación

- [Comportamiento, invariantes y límites](docs/behavior.md).
- [Configuración y contrato futuro de Discord](docs/configuration.md).
- [Desarrollo, arquitectura y pruebas](docs/development.md).
- [Operación, recuperación y pruebas reales](docs/operations.md).
- [Instrucciones de trabajo para agentes](AGENTS.md).

El servicio systemd incluido es legado; la instalación definitiva sigue pendiente.
Ver las [precauciones de ejecución](docs/operations.md#ejecución) antes de probarlo.
