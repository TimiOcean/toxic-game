"""Tests for the sound-effect player."""

from __future__ import annotations

from pathlib import Path

from toxic_game.config import SfxConfig
from toxic_game.hw.sfx import (
    NoOpSfxPlayer,
    PygameSfxPlayer,
    RecordingSfxPlayer,
    build_sfx_player,
    random_pitch_factor,
    resample_mono_pitch,
)


def test_noop_player_ignores_events() -> None:
    player = NoOpSfxPlayer()
    player.play("hit")
    player.play("perfect")
    player.play("miss")


def test_recording_player_records_order() -> None:
    player = RecordingSfxPlayer()
    player.play("hit")
    player.play("miss")
    assert player.events == ["hit", "miss"]


def test_missing_sfx_files_are_ignored(tmp_path: Path) -> None:
    config = SfxConfig(
        hit=tmp_path / "nope-hit.wav",
        perfect=None,
        miss=tmp_path / "nope-miss.wav",
        pitch_randomize=0.05,
    )
    player = build_sfx_player(config)
    # No sounds loaded -> playing must not raise.
    player.play("hit")
    player.play("perfect")
    player.play("miss")


def test_pygame_player_without_mixer_is_silent() -> None:
    config = SfxConfig(hit=None, perfect=None, miss=None, pitch_randomize=0.0)
    player = PygameSfxPlayer(config)
    player.play("hit")


def test_random_pitch_factor_is_within_range() -> None:
    assert random_pitch_factor(0.05, lambda: 0.0) == 0.95
    assert random_pitch_factor(0.05, lambda: 1.0) == 1.05
    assert random_pitch_factor(0.0, lambda: 0.5) == 1.0


def test_resample_mono_pitch_shortens_for_higher_pitch() -> None:
    samples = list(range(100))
    shifted = resample_mono_pitch(samples, 1.1)
    assert len(shifted) < len(samples)


def test_resample_mono_pitch_unchanged_at_unity() -> None:
    samples = [0, 1000, 2000, 3000, 4000]
    shifted = resample_mono_pitch(samples, 1.0)
    assert list(shifted) == samples
