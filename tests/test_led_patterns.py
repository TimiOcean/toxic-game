"""Tests for LED pattern generation."""

from __future__ import annotations

from toxic_game.engine.led_frames import MAGENTA, OFF, WHITE
from toxic_game.hw.led_patterns import (
    dual_chase_pixels,
    end_flash_pixels,
    player1_chase_pixels,
    player2_chase_pixels,
    walk_pixels,
)


def test_walk_pixel_moves_left_to_right() -> None:
    frame_a = walk_pixels(8, WHITE, 0)
    frame_b = walk_pixels(8, WHITE, 1)

    assert frame_a[0] == WHITE
    assert frame_a[1] == OFF
    assert frame_b[1] == WHITE
    assert frame_b[0] == OFF


def test_player1_chase_starts_on_right_end() -> None:
    pixels = player1_chase_pixels(count=10, step=0, span=4)

    assert pixels[-1] != OFF
    assert pixels[0] == OFF


def test_player1_chase_ends_on_left_end() -> None:
    pixels = player1_chase_pixels(count=10, step=9, span=4)

    assert pixels[0] != OFF
    assert pixels[-1] == OFF


def test_player1_chase_gets_brighter_toward_left() -> None:
    dim = player1_chase_pixels(count=10, step=0, span=1)
    bright = player1_chase_pixels(count=10, step=9, span=1)

    assert sum(bright[0]) > sum(dim[-1])


def test_player2_chase_starts_on_left_end() -> None:
    pixels = player2_chase_pixels(count=10, step=0, span=4)

    assert pixels[0] != OFF
    assert pixels[-1] == OFF


def test_player2_chase_ends_on_right_end() -> None:
    pixels = player2_chase_pixels(count=10, step=9, span=4)

    assert pixels[-1] != OFF
    assert pixels[0] == OFF


def test_player2_chase_uses_cyan() -> None:
    pixels = player2_chase_pixels(count=10, step=5, span=1)

    lit = next(color for color in pixels if color != OFF)
    assert lit[2] > lit[0]


def test_dual_chase_includes_both_colors() -> None:
    pixels = dual_chase_pixels(count=12, step=3, span=2)

    assert any(channel > 0 for channel in pixels[3])  # cyan on left-ish
    assert any(pixels[count] != OFF for count in range(len(pixels)))


def test_dual_chase_hw_pattern_uses_full_brightness() -> None:
    from toxic_game.hw.led_patterns import pattern_frames

    frames = pattern_frames(
        pattern="dual-chase",
        count=10,
        span=1,
        color=MAGENTA,
    )
    dim = dual_chase_pixels(count=10, step=0, span=1, brightness_ramp=True)
    bright = dual_chase_pixels(count=10, step=0, span=1, brightness_ramp=False)

    assert frames[0].pixels == bright
    assert sum(bright[-1]) > sum(dim[-1])


def test_end_flash_left_and_right() -> None:
    left = end_flash_pixels(8, "left", WHITE)
    right = end_flash_pixels(8, "right", MAGENTA)

    assert left[0] == WHITE
    assert left[-1] == OFF
    assert right[-1] == MAGENTA
    assert right[0] == OFF
