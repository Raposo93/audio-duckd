#!/usr/bin/env sh
# Compatibility launcher: all logic lives in audio_duckd.
exec "${PYTHON:-python3}" "$(dirname "$0")/linphone-duck.py" "$@"
