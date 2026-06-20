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


# Exponential fade for tail pixels relative to head brightness.
_TAIL_FADE = (0.50, 0.22, 0.10, 0.04)


def _merge_pixel(pixels: list[RgbPixel], index: int, color: RgbPixel) -> None:
    if color == OFF:
        return
    existing = pixels[index]
    pixels[index] = (
        max(existing[0], color[0]),
        max(existing[1], color[1]),
        max(existing[2], color[2]),
    )


def _head_brightness(
    *,
    head_index: int,
    count: int,
    travel_right_to_left: bool,
    brightness_ramp: bool,
    travel_brightness: float | None,
    beat_pulse: float,
) -> float:
    if travel_brightness is not None:
        brightness = min(max(travel_brightness, 0.0), 1.0)
    elif brightness_ramp:
        progress = (
            1.0 - (head_index / max(count - 1, 1))
            if travel_right_to_left
            else head_index / max(count - 1, 1)
        )
        brightness = min(max(progress, 0.0), 1.0)
    else:
        brightness = 1.0
    return brightness * min(max(beat_pulse, 0.0), 1.0)


def _place_span(
    pixels: list[RgbPixel],
    *,
    head_index: int,
    span: int,
    color: RgbPixel,
    travel_right_to_left: bool,
    brightness_ramp: bool,
    travel_brightness: float | None = None,
    beat_pulse: float = 1.0,
    tail_length: int = 0,
) -> None:
    count = len(pixels)
    if span <= 0 or count == 0:
        return

    if travel_right_to_left:
        start = max(head_index - span + 1, 0)
        end = head_index
    else:
        start = head_index
        end = min(head_index + span - 1, count - 1)

    brightness = _head_brightness(
        head_index=head_index,
        count=count,
        travel_right_to_left=travel_right_to_left,
        brightness_ramp=brightness_ramp,
        travel_brightness=travel_brightness,
        beat_pulse=beat_pulse,
    )
    lit = scale_pixel(color, brightness)
    for index in range(start, end + 1):
        pixels[index] = lit

    if tail_length <= 0:
        return

    for offset in range(1, tail_length + 1):
        fade_index = min(offset - 1, len(_TAIL_FADE) - 1)
        tail_brightness = brightness * _TAIL_FADE[fade_index]
        tail_color = scale_pixel(color, tail_brightness)
        if travel_right_to_left:
            tail_index = head_index + offset
        else:
            tail_index = head_index - offset
        if 0 <= tail_index < count:
            _merge_pixel(pixels, tail_index, tail_color)


def player1_chase_pixels(
    count: int,
    head_index: int,
    span: int,
    *,
    brightness_ramp: bool = True,
    travel_brightness: float | None = None,
    beat_pulse: float = 1.0,
    tail_length: int = 0,
) -> tuple[RgbPixel, ...]:
    """Magenta running light traveling right to left."""
    pixels = blank_pixels(count)
    clamped_head = max(span - 1, min(head_index, count - 1))
    _place_span(
        pixels,
        head_index=clamped_head,
        span=span,
        color=MAGENTA,
        travel_right_to_left=True,
        brightness_ramp=brightness_ramp,
        travel_brightness=travel_brightness,
        beat_pulse=beat_pulse,
        tail_length=tail_length,
    )
    return tuple(pixels)


def player2_chase_pixels(
    count: int,
    head_index: int,
    span: int,
    *,
    brightness_ramp: bool = True,
    travel_brightness: float | None = None,
    beat_pulse: float = 1.0,
    tail_length: int = 0,
) -> tuple[RgbPixel, ...]:
    """Cyan running light traveling left to right."""
    pixels = blank_pixels(count)
    clamped_head = max(0, min(head_index, count - span))
    _place_span(
        pixels,
        head_index=clamped_head,
        span=span,
        color=CYAN,
        travel_right_to_left=False,
        brightness_ramp=brightness_ramp,
        travel_brightness=travel_brightness,
        beat_pulse=beat_pulse,
        tail_length=tail_length,
    )
    return tuple(pixels)


def chase_pixels(
    count: int,
    head_index: int,
    span: int,
    color: RgbPixel,
    *,
    travel_right_to_left: bool,
    brightness_ramp: bool = True,
    travel_brightness: float | None = None,
    beat_pulse: float = 1.0,
    tail_length: int = 0,
) -> tuple[RgbPixel, ...]:
    """Render a running light of an arbitrary color at ``head_index``.

    Generic counterpart to :func:`player1_chase_pixels` /
    :func:`player2_chase_pixels` for callers (e.g. Pong) that need a freely
    chosen color instead of the fixed magenta/cyan player lights.
    """
    pixels = blank_pixels(count)
    if travel_right_to_left:
        clamped_head = max(span - 1, min(head_index, count - 1))
    else:
        clamped_head = max(0, min(head_index, count - span))
    _place_span(
        pixels,
        head_index=clamped_head,
        span=span,
        color=color,
        travel_right_to_left=travel_right_to_left,
        brightness_ramp=brightness_ramp,
        travel_brightness=travel_brightness,
        beat_pulse=beat_pulse,
        tail_length=tail_length,
    )
    return tuple(pixels)


def dual_chase_pixels(
    count: int,
    step: int,
    span: int,
    *,
    brightness_ramp: bool = True,
    tail_length: int = 0,
) -> tuple[RgbPixel, ...]:
    """Both player chase lights on one strip."""
    p1_head = max(count - 1 - step, span - 1)
    p2_head = min(step, count - span)
    pixels = list(
        player1_chase_pixels(
            count,
            p1_head,
            span,
            brightness_ramp=brightness_ramp,
            tail_length=tail_length,
        ),
    )
    for index, color in enumerate(
        player2_chase_pixels(
            count,
            p2_head,
            span,
            brightness_ramp=brightness_ramp,
            tail_length=tail_length,
        ),
    ):
        if color != OFF:
            _merge_pixel(pixels, index, color)
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
    tail_length: int = 0,
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
                    max(count - 1 - step, span - 1),
                    span,
                    brightness_ramp=brightness_ramp,
                    tail_length=tail_length,
                ),
            )
            for step in range(count)
        ]
    if pattern == "p2-chase":
        return [
            build_frame(
                player2_chase_pixels(
                    count,
                    min(step, count - span),
                    span,
                    brightness_ramp=brightness_ramp,
                    tail_length=tail_length,
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
                    tail_length=tail_length,
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
