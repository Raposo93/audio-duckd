"""Strict JSON configuration, independent of the audio server."""

from dataclasses import dataclass, field
import json
import math
from pathlib import Path


class ConfigError(ValueError):
    """Invalid configuration that can be reported directly to the user."""


def _number(name, value, *, minimum=None, maximum=None, positive=False):
    try:
        finite = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        finite = False
    if (not finite
            or (minimum is not None and value < minimum)
            or (maximum is not None and value > maximum)
            or (positive and value <= 0)):
        raise ConfigError(f"{name}: numeric value out of range ({value!r})")


def _selectors(name, values):
    if not isinstance(values, (list, tuple)) or not values:
        raise ConfigError(f"{name}: a non-empty list of binaries is required")
    for value in values:
        if (not isinstance(value, str) or not value or value != value.strip()
                or any(c.isspace() or ord(c) < 32 for c in value)
                or any(c in value for c in '/\\*?[]') or '\x7f' in value):
            raise ConfigError(f"{name}: invalid selector {value!r}; use the exact binary name")
    if len(set(values)) != len(values):
        raise ConfigError(f"{name}: duplicate selectors")
    return tuple(values)


@dataclass(frozen=True)
class Applications:
    linphone: tuple[str, ...] = ("linphone",)
    discord: tuple[str, ...] = ("Discord",)
    targets: tuple[str, ...] = ("brave",)

    def __post_init__(self):
        for name in ("linphone", "discord", "targets"):
            object.__setattr__(self, name, _selectors(f"applications.{name}", getattr(self, name)))
        groups = (self.linphone, self.discord, self.targets)
        if any(set(a) & set(b) for i, a in enumerate(groups) for b in groups[i + 1:]):
            raise ConfigError("applications: Linphone, Discord and targets must have disjoint selectors")


@dataclass(frozen=True)
class DiscordConfig:
    activation_threshold_dbfs: float = -40.0
    deactivation_threshold_dbfs: float = -45.0
    attack_seconds: float = 0.15
    release_seconds: float = 0.8
    sample_interval_seconds: float = 0.05

    def __post_init__(self):
        for name in ("activation_threshold_dbfs", "deactivation_threshold_dbfs"):
            _number(f"discord.{name}", getattr(self, name), maximum=0)
        if self.deactivation_threshold_dbfs > self.activation_threshold_dbfs:
            raise ConfigError("discord: deactivation_threshold_dbfs must be <= activation_threshold_dbfs")
        for name in ("attack_seconds", "release_seconds"):
            _number(f"discord.{name}", getattr(self, name), minimum=0)
        _number("discord.sample_interval_seconds", self.sample_interval_seconds, positive=True)


@dataclass(frozen=True)
class Config:
    applications: Applications = field(default_factory=Applications)
    attenuation_factor: float = 0.2
    discord: DiscordConfig = field(default_factory=DiscordConfig)

    def __post_init__(self):
        if not isinstance(self.applications, Applications) or not isinstance(self.discord, DiscordConfig):
            raise ConfigError("applications and discord must be valid configurations")
        _number("attenuation_factor", self.attenuation_factor, minimum=0, maximum=1)

    def is_target(self, binary: str) -> bool:
        apps = self.applications
        return binary in apps.targets and binary not in apps.linphone + apps.discord


def _object(value, allowed, name):
    if not isinstance(value, dict):
        raise ConfigError(f"{name}: a JSON object is required")
    unknown = value.keys() - allowed
    if unknown:
        raise ConfigError(f"{name}: unknown parameters: {', '.join(sorted(unknown))}")
    return value


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_config(path: str | Path | None = None) -> Config:
    if path is None:
        return Config()
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ConfigError(f"Could not read configuration {path}: {exc}") from exc
    data = _object(data, {"applications", "attenuation_factor", "discord"}, "config")
    apps = _object(data.get("applications", {}), {"linphone", "discord", "targets"}, "applications")
    discord = _object(data.get("discord", {}), set(DiscordConfig.__dataclass_fields__), "discord")
    return Config(Applications(**apps), data.get("attenuation_factor", 0.2), DiscordConfig(**discord))
