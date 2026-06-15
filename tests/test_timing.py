"""Tests for musical timing helpers."""

from __future__ import annotations

import pytest

from toxic_game.engine.timing import (
    SongTiming,
    absolute_beat_to_bar_beat,
    absolute_beat_to_ms,
    bar_beat_text_to_ms,
    bar_beat_to_absolute_beat,
    format_bar_beat,
    ms_to_absolute_beat,
    ms_to_bar_beat,
    parse_bar_beat,
)


@pytest.fixture
def timing_120() -> SongTiming:
    return SongTiming(bpm=120.0, delay_to_first_beat_ms=500)


def test_ms_per_beat_at_120_bpm() -> None:
    timing = SongTiming(bpm=120.0, delay_to_first_beat_ms=0)
    assert timing.ms_per_beat == 500.0


def test_ms_to_absolute_beat_respects_delay(timing_120: SongTiming) -> None:
    assert ms_to_absolute_beat(timing_120, 500) == 0.0
    assert ms_to_absolute_beat(timing_120, 1000) == 1.0
    assert ms_to_absolute_beat(timing_120, 0) == -1.0


def test_absolute_beat_to_ms_round_trip(timing_120: SongTiming) -> None:
    for beat in (0, 1, 3.5, 16):
        assert absolute_beat_to_ms(timing_120, beat) == pytest.approx(
            timing_120.delay_to_first_beat_ms + beat * timing_120.ms_per_beat,
        )


def test_parse_bar_beat() -> None:
    assert parse_bar_beat("3.2") == (3, 2)
    assert parse_bar_beat(" 1.4 ") == (1, 4)


def test_parse_bar_beat_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        parse_bar_beat("")
    with pytest.raises(ValueError):
        parse_bar_beat("3")
    with pytest.raises(ValueError):
        parse_bar_beat("0.1")


def test_bar_beat_to_absolute_beat() -> None:
    assert bar_beat_to_absolute_beat(1, 1) == 0
    assert bar_beat_to_absolute_beat(3, 2) == 9


def test_absolute_beat_to_bar_beat() -> None:
    assert absolute_beat_to_bar_beat(0) == (1, 1)
    assert absolute_beat_to_bar_beat(9) == (3, 2)


def test_format_bar_beat() -> None:
    assert format_bar_beat(3, 2) == "3.2"


def test_bar_beat_text_to_ms(timing_120: SongTiming) -> None:
    # Beat 9 starts at delay + 9 * 500ms = 5000ms
    assert bar_beat_text_to_ms(timing_120, "3.2") == 5000.0


def test_ms_to_bar_beat_before_first_beat(timing_120: SongTiming) -> None:
    assert ms_to_bar_beat(timing_120, 0) is None
    assert ms_to_bar_beat(timing_120, 499) is None


def test_ms_to_bar_beat_after_first_beat(timing_120: SongTiming) -> None:
    assert ms_to_bar_beat(timing_120, 500) == (1, 1)
    assert ms_to_bar_beat(timing_120, 5000) == (3, 2)
