"""Acceso estructurado a PulseAudio y pipewire-pulse mediante libpulse."""

from dataclasses import dataclass
from typing import Protocol


class BackendError(RuntimeError):
    pass


@dataclass(frozen=True)
class Stream:
    index: int
    direction: str
    binary: str
    client: int
    process_id: str
    volumes: tuple[float, ...]
    mute: bool = False
    corked: bool = False

    @property
    def identity(self) -> tuple:
        return self.direction, self.index, self.client, self.process_id, self.binary


class AudioBackend(Protocol):
    def streams(self) -> list[Stream]: ...

    def set_volume(self, stream: Stream, volumes: tuple[float, ...]) -> None: ...


class PulseBackend:
    def __init__(self):
        # La política y sus pruebas no necesitan cargar libpulse.
        import pulsectl

        self.api = pulsectl
        try:
            self.pulse = pulsectl.Pulse("audio-duckd")
        except pulsectl.PulseError as exc:
            raise BackendError(str(exc)) from exc

    @staticmethod
    def _stream(info, direction: str) -> Stream:
        props = info.proplist
        binary = props.get("application.process.binary", "").removesuffix(" (deleted)")
        return Stream(
            info.index, direction, binary, info.client,
            props.get("application.process.id", ""), tuple(info.volume.values),
            bool(info.mute), bool(info.corked),
        )

    def streams(self) -> list[Stream]:
        try:
            return [self._stream(s, "playback") for s in self.pulse.sink_input_list()] + [
                self._stream(s, "capture") for s in self.pulse.source_output_list()
            ]
        except self.api.PulseError as exc:
            raise BackendError(str(exc)) from exc

    def set_volume(self, stream: Stream, volumes: tuple[float, ...]) -> None:
        if stream.direction != "playback" or stream.binary != "brave":
            raise BackendError("Solo se permite modificar streams de reproducción de Brave")
        try:
            # Comprobar que el índice sigue perteneciendo al mismo stream.
            current = self._stream(self.pulse.sink_input_info(stream.index), "playback")
            if current.identity != stream.identity or len(current.volumes) != len(volumes):
                raise BackendError("El stream ha cambiado antes de escribir el volumen")
            self.pulse.sink_input_volume_set(
                stream.index, self.api.PulseVolumeInfo(list(volumes))
            )
        except self.api.PulseError as exc:
            raise BackendError(str(exc)) from exc

    def close(self) -> None:
        self.pulse.close()
