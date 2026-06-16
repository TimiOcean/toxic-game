"""Tests for tap note loading and spawn resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from toxic_game.engine.notes import (
    load_song_notes,
    load_tap_file,
    resolve_tap,
    spawn_ms_for_hit,
)
from toxic_game.engine.timing import SongTiming


@pytest.fixture
def timing() -> SongTiming:
    return SongTiming(bpm=120.0, delay_to_first_beat_ms=500)


def test_load_tap_file_parses_bar_beat(tmp_path: Path) -> None:
    tap_path = tmp_path / "p1.taps"
    tap_path.write_text("1.1\n3.2\n\n# comment\n", encoding="utf-8")

    assert load_tap_file(tap_path) == [(1, 1), (3, 2)]


def test_load_tap_file_missing_returns_empty(tmp_path: Path) -> None:
    assert load_tap_file(tmp_path / "missing.taps") == []


def test_load_tap_file_rejects_invalid_line(tmp_path: Path) -> None:
    tap_path = tmp_path / "p1.taps"
    tap_path.write_text("bad\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid tap"):
        load_tap_file(tap_path)


def test_spawn_ms_uses_lead_time_beats(timing: SongTiming) -> None:
    hit_ms = 2500.0
    assert spawn_ms_for_hit(hit_ms, timing, lead_time_beats=4) == 500


def test_resolve_tap_hit_and_spawn(timing: SongTiming) -> None:
    note = resolve_tap(1, 3, 2, timing, lead_time_beats=4)

    assert note.player == 1
    assert note.bar == 3
    assert note.beat == 2
    assert note.hit_ms == 5000
    assert note.spawn_ms == 3000


def test_load_song_notes_from_package(tmp_path: Path, timing: SongTiming) -> None:
    song_dir = tmp_path / "demo"
    song_dir.mkdir()
    (song_dir / "p1.taps").write_text("1.1\n", encoding="utf-8")
    (song_dir / "p2.taps").write_text("2.3\n", encoding="utf-8")

    notes = load_song_notes(song_dir, timing, lead_time_beats=4)

    assert len(notes.player1) == 1
    assert len(notes.player2) == 1
    assert notes.player1[0].hit_ms == 500
    assert notes.player2[0].hit_ms == 3500
    assert notes.all_notes[0].player == 1
