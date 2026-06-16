"""Tests for song package authoring CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from toxic_game.engine.song_config import load_song_config
from toxic_game.tools.song_config_tool import (
    SongPackageOptions,
    create_song_package,
    run_song_config_tool,
)


def test_create_song_package_writes_toml_and_copies_audio(tmp_path: Path) -> None:
    source = tmp_path / "source.mp3"
    source.write_bytes(b"ID3fake")

    song_dir = create_song_package(
        SongPackageOptions(
            song_id="demo",
            audio_source=source,
            name="Demo Song",
            bpm=128.0,
            delay_to_first_beat_ms=250,
        ),
        songs_dir=tmp_path / "songs",
    )

    config = load_song_config(song_dir)
    assert config.song_id == "demo"
    assert config.name == "Demo Song"
    assert config.bpm == 128.0
    assert config.delay_to_first_beat_ms == 250
    assert config.audio_path.read_bytes() == b"ID3fake"


def test_create_song_package_requires_audio(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        create_song_package(
            SongPackageOptions(
                song_id="demo",
                audio_source=tmp_path / "missing.mp3",
                name="Demo",
                bpm=120.0,
                delay_to_first_beat_ms=0,
            ),
            songs_dir=tmp_path / "songs",
        )


def test_run_song_config_tool_loads_package(tmp_path: Path) -> None:
    source = tmp_path / "track.ogg"
    source.write_bytes(b"fake")

    song_dir = run_song_config_tool(
        SongPackageOptions(
            song_id="toxic",
            audio_source=source,
            name="Toxic",
            bpm=143.6,
            delay_to_first_beat_ms=98,
        ),
        songs_dir=tmp_path / "songs",
    )

    assert (song_dir / "song.toml").exists()
    assert load_song_config(song_dir).name == "Toxic"
