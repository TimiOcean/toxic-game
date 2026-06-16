"""Diagnostic LED patterns for hardware bring-up."""

from __future__ import annotations

from typing import Literal

from toxic_game.engine.led_frames import (
    CYAN,
    MAGENTA,
    OFF,
    LedFrame,
    RgbPixel,
    blank_pixels,
    build_frame,
    scale_pixel,
)

Side = Literal["left", "right"]


def solid_pixels(count: int, color: RgbPixel) -> tuple[RgbPixel, ...]:
    """Fill the strip with one color."""
    return tuple(color for _ in range(count))


def walk_pixels(count: int, color: RgbPixel, step: int) -> tuple[RgbPixel, ...]:
    """Light a single pixel walking left to right (index 0 = left)."""
    pixels = blank_pixels(count)
    pixels[step % count] = color
    return tuple(pixels)


def _place_span(
    pixels: list[RgbPixel],
    *,
    head_index: int,
    span: int,
    color: RgbPixel,
    travel_right_to_left: bool,
    brightness_ramp: bool,
    beat_pulse: float = 1.0,
) -> None:
    count = len(pixels)
    if span <= 0 or count == 0:
        return

    if travel_right_to_left:
        start = max(head_index - span + 1, 0)
        end = head_index
        progress = 1.0 - (head_index / max(count - 1, 1))
    else:
        start = head_index
        end = min(head_index + span - 1, count - 1)
        progress = head_index / max(count - 1, 1)

    if brightness_ramp:
        brightness = 0.15 + 0.85 * min(max(progress, 0.0), 1.0)
    else:
        brightness = 1.0
    brightness *= min(max(beat_pulse, 0.0), 1.0)
    lit = scale_pixel(color, brightness)
    for index in range(start, end + 1):
        pixels[index] = lit


def player1_chase_pixels(
    count: int,
    step: int,
    span: int,
    *,
    brightness_ramp: bool = True,
    beat_pulse: float = 1.0,
) -> tuple[RgbPixel, ...]:
    """Magenta running light traveling right to left."""
    pixels = blank_pixels(count)
    head_index = max((count - 1) - (step % count), 0)
    _place_span(
        pixels,
        head_index=head_index,
        span=span,
        color=MAGENTA,
        travel_right_to_left=True,
        brightness_ramp=brightness_ramp,
        beat_pulse=beat_pulse,
    )
    return tuple(pixels)


def player2_chase_pixels(
    count: int,
    step: int,
    span: int,
    *,
    brightness_ramp: bool = True,
    beat_pulse: float = 1.0,
) -> tuple[RgbPixel, ...]:
    """Cyan running light traveling left to right."""
    pixels = blank_pixels(count)
    head_index = step % count
    _place_span(
        pixels,
        head_index=head_index,
        span=span,
        color=CYAN,
        travel_right_to_left=False,
        brightness_ramp=brightness_ramp,
        beat_pulse=beat_pulse,
    )
    return tuple(pixels)


def dual_chase_pixels(
    count: int,
    step: int,
    span: int,
    *,
    brightness_ramp: bool = True,
) -> tuple[RgbPixel, ...]:
    """Both player chase lights on one strip."""
    pixels = list(
        player1_chase_pixels(count, step, span, brightness_ramp=brightness_ramp),
    )
    for index, color in enumerate(
        player2_chase_pixels(count, step, span, brightness_ramp=brightness_ramp),
    ):
        if color != OFF:
            pixels[index] = color
    return tuple(pixels)


def end_flash_pixels(count: int, side: Side, color: RgbPixel) -> tuple[RgbPixel, ...]:
    """Flash one end of the strip."""
    pixels = blank_pixels(count)
    pixels[0 if side == "left" else count - 1] = color
    return tuple(pixels)


PRIMARY_COLOR_NAMES = ("red", "green", "blue", "white", "magenta")


def pattern_frames(
    *,
    pattern: str,
    count: int,
    span: int,
    color: RgbPixel,
    brightness_ramp: bool = False,
) -> list[LedFrame]:
    """Expand a named diagnostic pattern into frames."""
    if pattern == "solid":
        return [build_frame(solid_pixels(count, color))]
    if pattern == "walk":
        return [build_frame(walk_pixels(count, color, step)) for step in range(count)]
    if pattern == "p1-chase":
        return [
            build_frame(
                player1_chase_pixels(
                    count,
                    step,
                    span,
                    brightness_ramp=brightness_ramp,
                ),
            )
            for step in range(count)
        ]
    if pattern == "p2-chase":
        return [
            build_frame(
                player2_chase_pixels(
                    count,
                    step,
                    span,
                    brightness_ramp=brightness_ramp,
                ),
            )
            for step in range(count)
        ]
    if pattern == "dual-chase":
        return [
            build_frame(
                dual_chase_pixels(
                    count,
                    step,
                    span,
                    brightness_ramp=brightness_ramp,
                ),
            )
            for step in range(count)
        ]
    if pattern == "primaries":
        from toxic_game.engine.led_frames import NAMED_COLORS

        return [
            build_frame(solid_pixels(count, NAMED_COLORS[name]))
            for name in PRIMARY_COLOR_NAMES
        ]
    message = f"unsupported pattern: {pattern}"
    raise ValueError(message)
