"""Gameplay LED projection from active tap notes and hit feedback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from toxic_game.engine.led_frames import (
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
) -> tuple[RgbPixel, ...]:
    ratio = _travel_ratio(
        progress_ms=progress_ms,
        spawn_ms=note.spawn_ms,
        hit_ms=note.hit_ms,
    )
    if ratio is None:
        return tuple(OFF for _ in range(strip_len))

    step = round(ratio * max(strip_len - 1, 0))
    if note.player == 1:
        return player1_chase_pixels(strip_len, step, span, brightness_ramp=True)
    return player2_chase_pixels(strip_len, step, span, brightness_ramp=True)


def _feedback_color(judgement: Judgement) -> RgbPixel:
    if judgement == Judgement.ERROR:
        return RED
    return WHITE


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

    pixels = blank_pixels(strip_len)
    color = _feedback_color(feedback.judgement)
    if feedback.player == 1:
        pixels[0] = color
    else:
        pixels[strip_len - 1] = color
    return tuple(pixels)


def build_gameplay_frame(
    *,
    strip_len: int,
    span: int,
    progress_ms: int,
    notes: tuple[ResolvedNote, ...],
    feedback: tuple[HitFeedback, ...],
    hit_flash_ms: int,
) -> LedFrame:
    """Project active tap notes and judgement flashes onto the gameplay strip."""
    pixels = blank_pixels(strip_len)

    for note in notes:
        _merge_pixels(pixels, _note_travel_pixels(
            strip_len=strip_len,
            span=span,
            note=note,
            progress_ms=progress_ms,
        ))

    for flash in feedback:
        _merge_pixels(pixels, _feedback_flash_pixels(
            strip_len=strip_len,
            feedback=flash,
            progress_ms=progress_ms,
            hit_flash_ms=hit_flash_ms,
        ))

    return build_frame(pixels)
