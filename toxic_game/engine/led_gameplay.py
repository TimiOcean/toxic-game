"""Gameplay LED projection from active tap notes and hit feedback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from toxic_game.engine.led_frames import (
    GOLD,
    MAGENTA,
    OFF,
    RED,
    RgbPixel,
    WHITE,
    LedFrame,
    blank_pixels,
    build_frame,
)
from toxic_game.engine.notes import ResolvedNote
from toxic_game.engine.scoring import Judgement
from toxic_game.engine.timing import SongTiming, beat_pulse_brightness
from toxic_game.hw.led_patterns import player1_chase_pixels, player2_chase_pixels

PlayerId = Literal[1, 2]


@dataclass(frozen=True, slots=True)
class HitFeedback:
    """A short end-flash triggered by scoring judgement."""

    player: PlayerId
    started_ms: int
    judgement: Judgement


def _merge_pixels(
    base: list[RgbPixel],
    overlay: tuple[RgbPixel, ...],
) -> None:
    for index, color in enumerate(overlay):
        if color == OFF:
            continue
        existing = base[index]
        base[index] = (
            max(existing[0], color[0]),
            max(existing[1], color[1]),
            max(existing[2], color[2]),
        )


def _travel_ratio(*, progress_ms: int, spawn_ms: int, hit_ms: int) -> float | None:
    if progress_ms < spawn_ms or progress_ms >= hit_ms:
        return None
    travel_ms = max(hit_ms - spawn_ms, 1)
    return (progress_ms - spawn_ms) / travel_ms


def _note_travel_pixels(
    *,
    strip_len: int,
    span: int,
    note: ResolvedNote,
    progress_ms: int,
    timing: SongTiming | None,
) -> tuple[RgbPixel, ...]:
    ratio = _travel_ratio(
        progress_ms=progress_ms,
        spawn_ms=note.spawn_ms,
        hit_ms=note.hit_ms,
    )
    if ratio is None:
        return tuple(OFF for _ in range(strip_len))

    beat_pulse = (
        beat_pulse_brightness(timing, progress_ms)
        if timing is not None
        else 1.0
    )
    step = round(ratio * max(strip_len - 1, 0))
    if note.player == 1:
        return player1_chase_pixels(
            strip_len,
            step,
            span,
            brightness_ramp=True,
            beat_pulse=beat_pulse,
        )
    return player2_chase_pixels(
        strip_len,
        step,
        span,
        brightness_ramp=True,
        beat_pulse=beat_pulse,
    )


@dataclass(frozen=True, slots=True)
class _FeedbackStyle:
    """Visual parameters for one judgement flash."""

    base_color: RgbPixel
    start_size: int
    max_size: int
    has_sparkles: bool
    distance_falloff: float


def _feedback_style(*, judgement: Judgement, strip_len: int) -> _FeedbackStyle:
    """Return flash style scaled to the gameplay strip length."""
    if judgement == Judgement.PERFECT:
        return _FeedbackStyle(
            base_color=WHITE,
            start_size=1,
            max_size=max(3, round(strip_len * 0.35)),
            has_sparkles=True,
            distance_falloff=0.25,
        )
    if judgement == Judgement.GOOD:
        return _FeedbackStyle(
            base_color=GOLD,
            start_size=1,
            max_size=max(2, round(strip_len * 0.15)),
            has_sparkles=False,
            distance_falloff=0.5,
        )
    return _FeedbackStyle(
        base_color=RED,
        start_size=1,
        max_size=max(2, round(strip_len * 0.15)),
        has_sparkles=False,
        distance_falloff=0.5,
    )


def _triangular_peak_factor(*, t: float) -> float:
    """Triangle wave with peak at t=0.5 and zeros at t=0 and t=1."""
    # 0..1..0
    return 1.0 - abs(2.0 * t - 1.0)


def _sparkle_blanked(*, index: int, age_ms: int, distance_from_end: int) -> bool:
    """Deterministically blank some burst pixels to create a sparkle shimmer.

    The hit-end pixel is never blanked so the flash stays anchored.
    """
    if distance_from_end == 0:
        return False
    phase = age_ms // 40
    return (index * 7 + phase * 3) % 5 < 2


def _feedback_flash_pixels(
    *,
    strip_len: int,
    feedback: HitFeedback,
    progress_ms: int,
    hit_flash_ms: int,
) -> tuple[RgbPixel, ...]:
    age_ms = progress_ms - feedback.started_ms
    if age_ms < 0 or age_ms >= hit_flash_ms:
        return tuple(OFF for _ in range(strip_len))

    style = _feedback_style(judgement=feedback.judgement, strip_len=strip_len)
    max_size = max(1, min(strip_len, style.max_size))
    start_size = max(1, min(strip_len, style.start_size))

    t = age_ms / max(hit_flash_ms, 1)
    peak = _triangular_peak_factor(t=t)
    size = start_size + round((max_size - start_size) * peak)
    size = max(1, min(strip_len, size))

    pixels = blank_pixels(strip_len)
    if feedback.player == 1:
        lit_start = 0
        lit_end = size - 1
    else:
        lit_start = strip_len - size
        lit_end = strip_len - 1

    for index in range(lit_start, lit_end + 1):
        # Distance from the hit end: 0 at the end pixel.
        if feedback.player == 1:
            d = index - lit_start
        else:
            d = lit_end - index

        if style.has_sparkles and _sparkle_blanked(
            index=index,
            age_ms=age_ms,
            distance_from_end=d,
        ):
            # Sparkle: this pixel is fully off this frame.
            pixels[index] = OFF
            continue

        denom = max(size - 1, 1)
        distance_factor = 1.0 - (d / denom) * style.distance_falloff
        brightness = max(0.0, min(1.0, distance_factor))
        pixels[index] = (
            round(style.base_color[0] * brightness),
            round(style.base_color[1] * brightness),
            round(style.base_color[2] * brightness),
        )

    end_index = 0 if feedback.player == 1 else strip_len - 1
    pixels[end_index] = style.base_color
    return tuple(pixels)


def build_gameplay_frame(
    *,
    strip_len: int,
    span: int,
    progress_ms: int,
    notes: tuple[ResolvedNote, ...],
    feedback: tuple[HitFeedback, ...],
    hit_flash_ms: int,
    timing: SongTiming | None = None,
) -> LedFrame:
    """Project active tap notes and judgement flashes onto the gameplay strip."""
    pixels = blank_pixels(strip_len)

    for note in notes:
        _merge_pixels(pixels, _note_travel_pixels(
            strip_len=strip_len,
            span=span,
            note=note,
            progress_ms=progress_ms,
            timing=timing,
        ))

    for flash in feedback:
        _merge_pixels(pixels, _feedback_flash_pixels(
            strip_len=strip_len,
            feedback=flash,
            progress_ms=progress_ms,
            hit_flash_ms=hit_flash_ms,
        ))

    return build_frame(pixels)
