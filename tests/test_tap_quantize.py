"""Tests for tap quantization and tap file writing."""

from __future__ import annotations

from pathlib import Path

from toxic_game.engine.notes import load_song_notes, load_tap_file
from toxic_game.engine.tap_quantize import (
    RecordedTap,
    quantize_press_ms,
    quantize_recorded_taps,
    write_tap_files,
)
from toxic_game.engine.timing import SongTiming, bar_beat_text_to_ms


def _timing() -> SongTiming:
    return SongTiming(bpm=120.0, delay_to_first_beat_ms=500)


def test_quantize_press_ms_rounds_to_nearest_quarter() -> None:
    timing = _timing()

    assert quantize_press_ms(timing, 500) == (1, 1)
    assert quantize_press_ms(timing, 720) == (1, 1)
    assert quantize_press_ms(timing, 770) == (1, 2)
    assert quantize_press_ms(timing, 1000) == (1, 2)


def test_quantize_press_ms_ignores_pre_roll() -> None:
    timing = _timing()

    assert quantize_press_ms(timing, 400) is None


def test_quantize_recorded_taps_dedupes_and_sorts() -> None:
    timing = _timing()
    recordings = (
        RecordedTap(player=1, press_ms=1000),
        RecordedTap(player=1, press_ms=1010),
        RecordedTap(player=2, press_ms=1500),
    )

    p1_lines, p2_lines = quantize_recorded_taps(timing, recordings)

    assert p1_lines == ["1.2"]
    assert p2_lines == ["1.3"]


def test_write_tap_files_round_trip_through_notes_loader(tmp_path: Path) -> None:
    timing = _timing()
    song_dir = tmp_path / "demo"
    song_dir.mkdir()

    p1_lines, p2_lines = quantize_recorded_taps(
        timing,
        (
            RecordedTap(player=1, press_ms=1000),
            RecordedTap(player=2, press_ms=1500),
        ),
    )
    write_tap_files(song_dir, p1_lines=p1_lines, p2_lines=p2_lines)

    assert load_tap_file(song_dir / "p1.taps") == [(1, 2)]
    assert load_tap_file(song_dir / "p2.taps") == [(1, 3)]

    notes = load_song_notes(song_dir, timing=timing, lead_time_beats=4)
    assert notes.player1[0].hit_ms == round(bar_beat_text_to_ms(timing, "1.2"))
    assert notes.player2[0].hit_ms == round(bar_beat_text_to_ms(timing, "1.3"))
