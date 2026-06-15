"""Per-song configuration loaded from ``songs/<id>/song.toml``."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from toxic_game.config import build_path_config
from toxic_game.engine.timing import SongTiming


@dataclass(frozen=True, slots=True)
class SongConfig:
    """Metadata for one playable song."""

    song_id: str
    name: str
    audio_path: Path
    bpm: float
    delay_to_first_beat_ms: int

    @property
    def timing(self) -> SongTiming:
        """Return timing helpers for this song."""
        return SongTiming(
            bpm=self.bpm,
            delay_to_first_beat_ms=self.delay_to_first_beat_ms,
        )


def _read_float(table: dict[str, object], key: str, default: float) -> float:
    value = table.get(key, default)
    if type(value) in {int, float}:
        return float(value)
    return default


def _read_int(table: dict[str, object], key: str, default: int) -> int:
    value = table.get(key, default)
    if type(value) is int:
        return value
    return default


def _read_str(table: dict[str, object], key: str, default: str) -> str:
    value = table.get(key, default)
    if type(value) is str:
        return value
    return default


def load_song_config(song_dir: Path) -> SongConfig:
    """Load ``song.toml`` from a song package directory."""
    config_path = song_dir / "song.toml"
    if not config_path.exists():
        message = f"song config not found: {config_path}"
        raise FileNotFoundError(message)

    document = tomllib.loads(config_path.read_text(encoding="utf-8"))
    audio_name = _read_str(document, "audio", "")
    if not audio_name:
        message = "song.toml must include an audio file path"
        raise ValueError(message)

    audio_path = (song_dir / audio_name).resolve()
    bpm = _read_float(document, "bpm", 120.0)
    if bpm <= 0:
        message = "bpm must be > 0"
        raise ValueError(message)

    return SongConfig(
        song_id=song_dir.name,
        name=_read_str(document, "name", song_dir.name),
        audio_path=audio_path,
        bpm=bpm,
        delay_to_first_beat_ms=_read_int(document, "delay_to_first_beat_ms", 0),
    )


def resolve_song_dir(song_id: str, *, songs_dir: Path | None = None) -> Path:
    """Resolve a song id to its package directory."""
    root = songs_dir or build_path_config().songs_dir
    return (root / song_id).resolve()


def load_song_by_id(song_id: str, *, songs_dir: Path | None = None) -> SongConfig:
    """Load a song package by id from the configured songs directory."""
    return load_song_config(resolve_song_dir(song_id, songs_dir=songs_dir))
