"""Save, proportionally attenuate and restore each target stream."""

import logging
from math import isclose

from .backend import AudioBackend, BackendError, Stream
from .config import Config
from .detection import target_playback, linphone_active

log = logging.getLogger(__name__)


class DuckingPolicy:
    def __init__(self, backend: AudioBackend, config: Config | None = None):
        self.backend = backend
        self.config = config if config is not None else Config()
        self.saved: dict[tuple, tuple[float, ...]] = {}

    def _write(self, stream: Stream, volumes: tuple[float, ...]) -> bool:
        try:
            self.backend.set_volume(stream, volumes)
        except BackendError as exc:
            log.warning("Could not change target id=%s: %s", stream.index, exc)
            return False
        return True

    def refresh(self, *, restoring: bool = False) -> None:
        streams = self.backend.streams()
        targets = {s.identity: s for s in target_playback(streams, self.config)}
        # Do not transfer a disappeared stream volume to a new stream.
        self.saved = {key: value for key, value in self.saved.items() if key in targets}
        active = not restoring and linphone_active(streams, self.config)
        if active:
            for key, stream in targets.items():
                original = self.saved.get(key, stream.volumes)
                desired = tuple(v * self.config.attenuation_factor for v in original)
                if len(original) != len(stream.volumes):
                    log.warning("Channel count changed for target id=%s", stream.index)
                    continue
                equal = all(isclose(v, target, abs_tol=1 / 65536)
                            for v, target in zip(stream.volumes, desired))
                if equal or self._write(stream, desired):
                    if key not in self.saved:
                        log.info("Linphone active: target id=%s, factor=%s",
                                 stream.index, self.config.attenuation_factor)
                    self.saved[key] = original
        else:
            for key, original in list(self.saved.items()):
                if self._write(targets[key], original):
                    log.info("Restored target id=%s", targets[key].index)
                    del self.saved[key]
