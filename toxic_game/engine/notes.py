"""Tap note loading and hit/spawn time resolution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from toxic_game.engine.timing import (
    SongTiming,
    bar_beat_text_to_ms,
    parse_bar_beat,
)

PlayerId = Literal[1, 2]


@dataclass(frozen=True, slots=True)
class ResolvedNote:
    """One tap note with playback times in milliseconds."""

    player: PlayerId
    bar: int
    beat: int
    hit_ms: int
    spawn_ms: int


@dataclass(frozen=True, slots=True)
class SongNotes:
    """All tap notes for a song package."""

    player1: tuple[ResolvedNote, ...]
    player2: tuple[ResolvedNote, ...]

    @property
    def all_notes(self) -> tuple[ResolvedNote, ...]:
        """Return both player note lists in hit-time order."""
        return tuple(sorted((*self.player1, *self.player2), key=lambda note: note.hit_ms))


def load_tap_file(path: Path) -> list[tuple[int, int]]:
    """Load ``bar.beat`` coordinates from a tap file."""
    if not path.exists():
        return []

    taps: list[tuple[int, int]] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            taps.append(parse_bar_beat(line))
        except ValueError as exc:
            message = f"invalid tap at {path}:{line_number}: {line!r}"
            raise ValueError(message) from exc
    return taps


def spawn_ms_for_hit(hit_ms: float, timing: SongTiming, *, lead_time_beats: int) -> int:
    """Return when a note's running light should appear before the hit."""
    lead_ms = lead_time_beats * timing.ms_per_beat
    return max(round(hit_ms - lead_ms), 0)


def resolve_tap(
    player: PlayerId,
    bar: int,
    beat: int,
    timing: SongTiming,
    *,
    lead_time_beats: int,
) -> ResolvedNote:
    """Convert one tap coordinate into hit and spawn times."""
    hit_ms = round(bar_beat_text_to_ms(timing, f"{bar}.{beat}"))
    return ResolvedNote(
        player=player,
        bar=bar,
        beat=beat,
        hit_ms=hit_ms,
        spawn_ms=spawn_ms_for_hit(hit_ms, timing, lead_time_beats=lead_time_beats),
    )


def resolve_taps(
    taps: list[tuple[int, int]],
    timing: SongTiming,
    *,
    player: PlayerId,
    lead_time_beats: int,
) -> tuple[ResolvedNote, ...]:
    """Resolve tap coordinates for one player."""
    return tuple(
        resolve_tap(
            player,
            bar,
            beat,
            timing,
            lead_time_beats=lead_time_beats,
        )
        for bar, beat in taps
    )


def load_song_notes(
    song_dir: Path,
    timing: SongTiming,
    *,
    lead_time_beats: int,
) -> SongNotes:
    """Load ``p1.taps`` and ``p2.taps`` from a song package directory."""
    player1 = resolve_taps(
        load_tap_file(song_dir / "p1.taps"),
        timing,
        player=1,
        lead_time_beats=lead_time_beats,
    )
    player2 = resolve_taps(
        load_tap_file(song_dir / "p2.taps"),
        timing,
        player=2,
        lead_time_beats=lead_time_beats,
    )
    return SongNotes(player1=player1, player2=player2)
