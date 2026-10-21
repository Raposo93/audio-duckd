"""Guardar, mantener al 20 % y restaurar cada stream de Brave por separado."""

import logging
from math import isclose

from .backend import AudioBackend, BackendError, Stream
from .detection import brave_playback, linphone_active

log = logging.getLogger(__name__)


class DuckingPolicy:
    def __init__(self, backend: AudioBackend):
        self.backend = backend
        self.saved: dict[tuple, tuple[float, ...]] = {}

    def _write(self, stream: Stream, volumes: tuple[float, ...]) -> bool:
        try:
            self.backend.set_volume(stream, volumes)
        except BackendError as exc:
            log.warning("No se pudo cambiar Brave id=%s: %s", stream.index, exc)
            return False
        return True

    def refresh(self, *, restoring: bool = False) -> None:
        streams = self.backend.streams()
        targets = {s.identity: s for s in brave_playback(streams)}
        # No transferir el volumen de un stream desaparecido a otro nuevo.
        self.saved = {key: value for key, value in self.saved.items() if key in targets}
        active = not restoring and linphone_active(streams)
        if active:
            for key, stream in targets.items():
                original = self.saved.get(key, stream.volumes)
                desired = (0.2,) * len(stream.volumes)
                if len(original) != len(desired):
                    log.warning("Cambió el número de canales de Brave id=%s", stream.index)
                    continue
                equal = all(isclose(v, 0.2, abs_tol=1 / 65536) for v in stream.volumes)
                if equal or self._write(stream, desired):
                    if key not in self.saved:
                        log.info("Linphone activo: Brave id=%s -> 20 %%", stream.index)
                    self.saved[key] = original
        else:
            for key, original in list(self.saved.items()):
                if self._write(targets[key], original):
                    log.info("Restaurado Brave id=%s", targets[key].index)
                    del self.saved[key]
