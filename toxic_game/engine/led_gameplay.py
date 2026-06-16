"""Gameplay LED projection from active tap notes."""

from __future__ import annotations

from toxic_game.engine.led_frames import (
    CYAN,
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
from toxic_game.hw.led_patterns import player1_chase_pixels, player2_chase_pixels


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


def _flash_pixels(
    *,
    strip_len: int,
    note: ResolvedNote,
    progress_ms: int,
    hit_flash_ms: int,
) -> tuple[RgbPixel, ...]:
    age_ms = progress_ms - note.hit_ms
    if age_ms < 0 or age_ms >= hit_flash_ms:
        return tuple(OFF for _ in range(strip_len))

    pixels = blank_pixels(strip_len)
    if note.player == 1:
        pixels[0] = WHITE
    else:
        pixels[strip_len - 1] = RED
    return tuple(pixels)


def build_gameplay_frame(
    *,
    strip_len: int,
    span: int,
    progress_ms: int,
    notes: tuple[ResolvedNote, ...],
    hit_flash_ms: int,
) -> LedFrame:
    """Project active tap notes and hit flashes onto the gameplay strip."""
    pixels = blank_pixels(strip_len)

    for note in notes:
        _merge_pixels(pixels, _note_travel_pixels(
            strip_len=strip_len,
            span=span,
            note=note,
            progress_ms=progress_ms,
        ))

    for note in notes:
        _merge_pixels(pixels, _flash_pixels(
            strip_len=strip_len,
            note=note,
            progress_ms=progress_ms,
            hit_flash_ms=hit_flash_ms,
        ))

    return build_frame(pixels)
