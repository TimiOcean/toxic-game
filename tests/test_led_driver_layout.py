"""Tests for dual-chase mapping and RGB/RGBW driver layout."""

from __future__ import annotations

from toxic_game.config import load_app_config
from toxic_game.engine.led_frames import build_frame
from toxic_game.hw.led_output import build_driver_pixels
from toxic_game.hw.led_patterns import dual_chase_pixels


def test_muted_rgbw_count_clocks_through_rgb_segment() -> None:
    config = load_app_config()

    assert config.led.muted_rgbw_count * 4 == config.led.muted_rgb_count * 3


def test_dual_chase_step_zero_lights_both_gameplay_ends() -> None:
    frame = build_frame(dual_chase_pixels(60, 0, 4, brightness_ramp=False))
    pixels = build_driver_pixels(frame, muted_rgbw_count=45, rgbw_count=60)

    assert len(pixels) == 105
    assert all(channel == 0 for pixel in pixels[:45] for channel in pixel)

    lit = [index - 45 for index, pixel in enumerate(pixels) if pixel != (0, 0, 0)]
    assert lit[:4] == [0, 1, 2, 3]
    assert lit[-4:] == [56, 57, 58, 59]
