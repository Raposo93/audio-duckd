"""Stream presence approximates call activity without measuring signal levels."""

from .backend import Stream
from .config import Config


def linphone_active(streams: list[Stream], config: Config) -> bool:
    return any(stream.binary in config.applications.linphone for stream in streams)


def target_playback(streams: list[Stream], config: Config) -> list[Stream]:
    return [s for s in streams if s.direction == "playback" and config.is_target(s.binary)]
