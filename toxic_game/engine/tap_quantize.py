"""Quantize live press times to bar.beat tap markers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from toxic_game.engine.timing import (
    SongTiming,
    absolute_beat_to_bar_beat,
    format_bar_beat,
    ms_to_absolute_beat,
)

PlayerId = Literal[1, 2]


@dataclass(frozen=True, slots=True)
class RecordedTap:
    """One raw button press captured during tap recording."""

    player: PlayerId
    press_ms: int


def quantize_press_ms(
    timing: SongTiming,
    press_ms: int,
) -> tuple[int, int] | None:
    """Quantize a press time to the nearest quarter-note ``bar.beat``."""
    absolute_beat = ms_to_absolute_beat(timing, press_ms)
    if absolute_beat < 0:
        return None

    rounded_beat = round(absolute_beat)
    if rounded_beat < 0:
        return None
    return absolute_beat_to_bar_beat(
        int(rounded_beat),
        beats_per_bar=timing.beats_per_bar,
    )


def quantize_recorded_taps(
    timing: SongTiming,
    recordings: tuple[RecordedTap, ...],
) -> tuple[list[str], list[str]]:
    """Return sorted unique ``bar.beat`` lines for each player."""
    p1_lines: list[str] = []
    p2_lines: list[str] = []

    for tap in sorted(recordings, key=lambda item: item.press_ms):
        coords = quantize_press_ms(timing, tap.press_ms)
        if coords is None:
            continue
        line = format_bar_beat(*coords)
        if tap.player == 1:
            if line not in p1_lines:
                p1_lines.append(line)
        elif line not in p2_lines:
            p2_lines.append(line)

    return p1_lines, p2_lines


def write_tap_file(path: Path, lines: list[str]) -> None:
    """Write one tap note file."""
    path.write_text(
        "\n".join(lines) + ("\n" if lines else ""),
        encoding="utf-8",
    )


def write_tap_files(
    song_dir: Path,
    *,
    p1_lines: list[str],
    p2_lines: list[str],
) -> tuple[Path, Path]:
    """Write ``p1.taps`` and ``p2.taps`` into a song package."""
    p1_path = song_dir / "p1.taps"
    p2_path = song_dir / "p2.taps"
    write_tap_file(p1_path, p1_lines)
    write_tap_file(p2_path, p2_lines)
    return p1_path, p2_path
