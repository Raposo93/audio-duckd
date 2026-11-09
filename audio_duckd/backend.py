"""Structured access to PulseAudio and pipewire-pulse through libpulse."""

from dataclasses import dataclass
from typing import NoReturn, Protocol

from .config import Config


class BackendError(RuntimeError):
    pass


class BackendDisconnected(BackendError):
    """The connection was lost; stream identities from it are no longer usable."""


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
    def __init__(self, config: Config | None = None):
        self.config = config if config is not None else Config()
        # The policy and its tests do not need to load libpulse.
        import pulsectl

        self.api = pulsectl
        self.pulse = pulsectl.Pulse("audio-duckd", connect=False)
        try:
            self.pulse.connect(autospawn=False, timeout=2.0)
        except pulsectl.PulseError as exc:
            self.pulse.close()
            raise BackendDisconnected(str(exc)) from exc

    def _check_connected(self) -> None:
        if not self.pulse.connected:
            raise BackendDisconnected("Audio server connection lost")

    def _raise_operation_error(self, exc: Exception) -> NoReturn:
        error = BackendError if self.pulse.connected else BackendDisconnected
        raise error(str(exc)) from exc

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
        self._check_connected()
        try:
            streams = [self._stream(s, "playback") for s in self.pulse.sink_input_list()]
            self._check_connected()
            streams += [
                self._stream(s, "capture") for s in self.pulse.source_output_list()
            ]
        except self.api.PulseError as exc:
            self._raise_operation_error(exc)
        self._check_connected()
        return streams

    def set_volume(self, stream: Stream, volumes: tuple[float, ...]) -> None:
        if stream.direction != "playback" or not self.config.is_target(stream.binary):
            raise BackendError("Only target application playback streams may be modified")
        self._check_connected()
        try:
            # Check that the index still belongs to the same stream.
            current = self._stream(self.pulse.sink_input_info(stream.index), "playback")
            if current.identity != stream.identity or len(current.volumes) != len(volumes):
                raise BackendError("The stream changed before the volume write")
            self._check_connected()
            self.pulse.sink_input_volume_set(
                stream.index, self.api.PulseVolumeInfo(list(volumes))
            )
        except self.api.PulseError as exc:
            self._raise_operation_error(exc)
        self._check_connected()

    def close(self) -> None:
        self.pulse.close()
