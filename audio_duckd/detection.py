"""La presencia de streams aproxima el estado de llamada, sin medir señal."""

from .backend import Stream


def linphone_active(streams: list[Stream]) -> bool:
    return any(stream.binary == "linphone" for stream in streams)


def brave_playback(streams: list[Stream]) -> list[Stream]:
    return [s for s in streams if s.direction == "playback" and s.binary == "brave"]
