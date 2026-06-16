"""Musical timing helpers for song playback."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_BEATS_PER_BAR = 4
BEAT_PULSE_PEAK = 1.0
BEAT_PULSE_FLOOR = 0.15
BEAT_PULSE_CYCLE_BEATS = 2


@dataclass(frozen=True, slots=True)
class SongTiming:
    """Timing parameters shared by a song."""

    bpm: float
    delay_to_first_beat_ms: int
    beats_per_bar: int = DEFAULT_BEATS_PER_BAR

    def __post_init__(self) -> None:
        if self.bpm <= 0:
            message = "bpm must be > 0"
            raise ValueError(message)
        if self.delay_to_first_beat_ms < 0:
            message = "delay_to_first_beat_ms must be >= 0"
            raise ValueError(message)
        if self.beats_per_bar < 1:
            message = "beats_per_bar must be >= 1"
            raise ValueError(message)

    @property
    def ms_per_beat(self) -> float:
        """Milliseconds between quarter-note beats."""
        return 60_000.0 / self.bpm


def ms_to_absolute_beat(timing: SongTiming, playback_ms: int) -> float:
    """Convert audio playback time to a floating-point absolute beat index."""
    return (playback_ms - timing.delay_to_first_beat_ms) / timing.ms_per_beat


def absolute_beat_to_ms(timing: SongTiming, beat: float) -> float:
    """Convert an absolute beat index to audio playback time in milliseconds."""
    return timing.delay_to_first_beat_ms + beat * timing.ms_per_beat


def parse_bar_beat(text: str) -> tuple[int, int]:
    """Parse ``bar.beat`` notation into 1-based bar and beat numbers."""
    cleaned = text.strip()
    if not cleaned:
        message = "bar.beat value must not be empty"
        raise ValueError(message)

    parts = cleaned.split(".", maxsplit=1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        message = f"invalid bar.beat notation: {text!r}"
        raise ValueError(message)

    bar_text, beat_text = parts
    if not bar_text.isdigit() or not beat_text.isdigit():
        message = f"invalid bar.beat notation: {text!r}"
        raise ValueError(message)

    bar = int(bar_text)
    beat = int(beat_text)
    if bar < 1 or beat < 1:
        message = f"bar and beat must be >= 1: {text!r}"
        raise ValueError(message)
    return bar, beat


def bar_beat_to_absolute_beat(
    bar: int,
    beat: int,
    *,
    beats_per_bar: int = DEFAULT_BEATS_PER_BAR,
) -> int:
    """Convert 1-based bar.beat coordinates to a zero-based absolute beat index."""
    if bar < 1 or beat < 1:
        message = "bar and beat must be >= 1"
        raise ValueError(message)
    if beat > beats_per_bar:
        message = f"beat must be <= {beats_per_bar}"
        raise ValueError(message)
    return (bar - 1) * beats_per_bar + (beat - 1)


def absolute_beat_to_bar_beat(
    absolute_beat: int,
    *,
    beats_per_bar: int = DEFAULT_BEATS_PER_BAR,
) -> tuple[int, int]:
    """Convert a zero-based absolute beat index to 1-based bar.beat coordinates."""
    if absolute_beat < 0:
        message = "absolute_beat must be >= 0"
        raise ValueError(message)
    bar = absolute_beat // beats_per_bar + 1
    beat = absolute_beat % beats_per_bar + 1
    return bar, beat


def format_bar_beat(bar: int, beat: int) -> str:
    """Format 1-based bar and beat numbers as ``bar.beat`` text."""
    return f"{bar}.{beat}"


def bar_beat_text_to_ms(timing: SongTiming, text: str) -> float:
    """Convert a ``bar.beat`` marker to playback time in milliseconds."""
    bar, beat = parse_bar_beat(text)
    absolute_beat = bar_beat_to_absolute_beat(
        bar,
        beat,
        beats_per_bar=timing.beats_per_bar,
    )
    return absolute_beat_to_ms(timing, absolute_beat)


def beat_pulse_brightness(timing: SongTiming, playback_ms: int) -> float:
    """Return running-light brightness for the current beat phase.

    Peaks at 100% every two beats, linear fade to 15% by the next even downbeat,
    then jumps back to 100%.
    """
    absolute_beat = ms_to_absolute_beat(timing, playback_ms)
    if absolute_beat < 0:
        return BEAT_PULSE_PEAK

    cycle_fraction = (absolute_beat % BEAT_PULSE_CYCLE_BEATS) / BEAT_PULSE_CYCLE_BEATS
    span = BEAT_PULSE_PEAK - BEAT_PULSE_FLOOR
    return BEAT_PULSE_PEAK - cycle_fraction * span


def ms_to_bar_beat(timing: SongTiming, playback_ms: int) -> tuple[int, int] | None:
    """Return the current 1-based bar.beat at playback time, if on or after beat 0."""
    absolute_beat = ms_to_absolute_beat(timing, playback_ms)
    if absolute_beat < 0:
        return None
    return absolute_beat_to_bar_beat(
        int(absolute_beat),
        beats_per_bar=timing.beats_per_bar,
    )
