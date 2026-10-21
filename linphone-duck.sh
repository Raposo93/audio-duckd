#!/usr/bin/env sh
# Lanzador de compatibilidad: toda la lógica está en audio_duckd.
exec "${PYTHON:-python3}" "$(dirname "$0")/linphone-duck.py" "$@"
