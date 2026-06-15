"""Tests for per-song configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from toxic_game.engine.song_config import load_song_config


def _write_song(tmp_path: Path, *, audio: str = "track.ogg", delay: int = 250) -> Path:
    song_dir = tmp_path / "demo"
    song_dir.mkdir()
    (song_dir / "song.toml").write_text(
        "\n".join(
            [
                'name = "Demo Song"',
                f'audio = "{audio}"',
                "bpm = 128.0",
                f"delay_to_first_beat_ms = {delay}",
            ],
        ),
        encoding="utf-8",
    )
    (song_dir / audio).write_bytes(b"fake")
    return song_dir


def test_load_song_config(tmp_path: Path) -> None:
    song_dir = _write_song(tmp_path)

    config = load_song_config(song_dir)

    assert config.song_id == "demo"
    assert config.name == "Demo Song"
    assert config.audio_path == (song_dir / "track.ogg").resolve()
    assert config.bpm == 128.0
    assert config.delay_to_first_beat_ms == 250
    assert config.timing.bpm == 128.0


def test_load_song_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_song_config(tmp_path / "missing")


def test_load_song_config_requires_audio(tmp_path: Path) -> None:
    song_dir = tmp_path / "empty"
    song_dir.mkdir()
    (song_dir / "song.toml").write_text('name = "No Audio"\n', encoding="utf-8")

    with pytest.raises(ValueError, match="audio"):
        load_song_config(song_dir)
