"""Gameplay LED projection from active tap notes and hit feedback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from toxic_game.config import LedConfig
from toxic_game.engine.led_frames import (
    CYAN,
    GOLD,
    MAGENTA,
    OFF,
    RED,
    RgbPixel,
    WHITE,
    LedFrame,
    blank_pixels,
    build_frame,
    scale_pixel,
)
from toxic_game.engine.notes import ResolvedNote
from toxic_game.engine.scoring import Judgement
from toxic_game.engine.timing import SongTiming, beat_pulse_brightness
from toxic_game.hw.led_patterns import player1_chase_pixels, player2_chase_pixels

PlayerId = Literal[1, 2]

MARKER_INTENSITY = 0.15


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


def hit_marker_range(
    *,
    player: PlayerId,
    strip_len: int,
    span: int,
    fraction: float,
) -> tuple[int, int]:
    """Return inclusive LED indices for the static hit marker on one side."""
    offset = max(0, round((strip_len - 1) * fraction))
    if player == 1:
        start = offset
        end = min(start + span - 1, strip_len - 1)
    else:
        end = strip_len - 1 - offset
        start = max(end - span + 1, 0)
    return start, end


def _travel_ratio(
    *,
    progress_ms: int,
    spawn_ms: int,
    hit_ms: int,
) -> float | None:
    if progress_ms < spawn_ms or progress_ms > hit_ms:
        return None

    travel_ms = max(hit_ms - spawn_ms, 1)
    return (progress_ms - spawn_ms) / travel_ms


def _active_feedback_players(
    feedback: tuple[HitFeedback, ...],
    *,
    progress_ms: int,
    led: LedConfig,
) -> frozenset[PlayerId]:
    active: set[PlayerId] = set()
    for flash in feedback:
        age_ms = progress_ms - flash.started_ms
        if 0 <= age_ms < led.hit_flash_ms:
            active.add(flash.player)
    return frozenset(active)


def _static_marker_pixels(
    *,
    strip_len: int,
    span: int,
    led: LedConfig,
    hidden_players: frozenset[PlayerId] = frozenset(),
) -> tuple[RgbPixel, ...]:
    pixels = blank_pixels(strip_len)
    for player, color in ((1, MAGENTA), (2, CYAN)):
        if player in hidden_players:
            continue
        start, end = hit_marker_range(
            player=player,  # type: ignore[arg-type]
            strip_len=strip_len,
            span=span,
            fraction=led.hit_marker_fraction,
        )
        lit = scale_pixel(color, MARKER_INTENSITY)
        for index in range(start, end + 1):
            pixels[index] = lit
    return tuple(pixels)


def _note_travel_pixels(
    *,
    strip_len: int,
    span: int,
    note: ResolvedNote,
    progress_ms: int,
    timing: SongTiming | None,
    led: LedConfig,
) -> tuple[RgbPixel, ...]:
    ratio = _travel_ratio(
        progress_ms=progress_ms,
        spawn_ms=note.spawn_ms,
        hit_ms=note.hit_ms,
    )
    if ratio is None:
        return tuple(OFF for _ in range(strip_len))

    marker_start, marker_end = hit_marker_range(
        player=note.player,  # type: ignore[arg-type]
        strip_len=strip_len,
        span=span,
        fraction=led.hit_marker_fraction,
    )
    beat_pulse = (
        beat_pulse_brightness(timing, progress_ms)
        if timing is not None
        else 1.0
    )

    if note.player == 1:
        marker_head = marker_end
        max_step = max((strip_len - 1) - marker_head, 0)
        head_index = (strip_len - 1) - round(ratio * max_step)
        return player1_chase_pixels(
            strip_len,
            head_index,
            span,
            brightness_ramp=True,
            beat_pulse=beat_pulse,
        )

    max_step = max(marker_start, 0)
    head_index = round(ratio * max_step)
    return player2_chase_pixels(
        strip_len,
        head_index,
        span,
        brightness_ramp=True,
        beat_pulse=beat_pulse,
    )


def _triangular_peak_factor(*, t: float) -> float:
    """Triangle wave with peak at t=0.5 and zeros at t=0 and t=1."""
    return 1.0 - abs(2.0 * t - 1.0)


@dataclass(frozen=True, slots=True)
class _FeedbackStyle:
    """Visual parameters for one judgement flash."""

    base_color: RgbPixel
    start_size: int
    max_size: int
    distance_falloff: float


def _feedback_style(*, judgement: Judgement, strip_len: int) -> _FeedbackStyle:
    """Return flash style scaled to the gameplay strip length."""
    if judgement == Judgement.PERFECT:
        base_color = WHITE
    elif judgement == Judgement.GOOD:
        base_color = GOLD
    else:
        base_color = RED
    return _FeedbackStyle(
        base_color=base_color,
        start_size=1,
        max_size=max(2, round(strip_len * 0.15)),
        distance_falloff=0.5,
    )


def _feedback_flash_pixels(
    *,
    strip_len: int,
    feedback: HitFeedback,
    progress_ms: int,
    led: LedConfig,
) -> tuple[RgbPixel, ...]:
    age_ms = progress_ms - feedback.started_ms
    if age_ms < 0 or age_ms >= led.hit_flash_ms:
        return tuple(OFF for _ in range(strip_len))

    style = _feedback_style(judgement=feedback.judgement, strip_len=strip_len)
    max_size = max(1, min(strip_len, style.max_size))
    start_size = max(1, min(strip_len, style.start_size))

    t = age_ms / max(led.hit_flash_ms, 1)
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
        if feedback.player == 1:
            d = index - lit_start
        else:
            d = lit_end - index

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


def feedback_duration_ms(feedback: HitFeedback, led: LedConfig) -> int:
    """Return how long one feedback entry stays visible."""
    return led.hit_flash_ms


def build_gameplay_frame(
    *,
    strip_len: int,
    span: int,
    progress_ms: int,
    notes: tuple[ResolvedNote, ...],
    feedback: tuple[HitFeedback, ...],
    led: LedConfig,
    timing: SongTiming | None = None,
) -> LedFrame:
    """Project active tap notes and judgement flashes onto the gameplay strip."""
    hidden_markers = _active_feedback_players(
        feedback,
        progress_ms=progress_ms,
        led=led,
    )
    pixels = list(_static_marker_pixels(
        strip_len=strip_len,
        span=span,
        led=led,
        hidden_players=hidden_markers,
    ))

    for note in notes:
        _merge_pixels(pixels, _note_travel_pixels(
            strip_len=strip_len,
            span=span,
            note=note,
            progress_ms=progress_ms,
            timing=timing,
            led=led,
        ))

    for flash in feedback:
        _merge_pixels(pixels, _feedback_flash_pixels(
            strip_len=strip_len,
            feedback=flash,
            progress_ms=progress_ms,
            led=led,
        ))

    return build_frame(pixels)
