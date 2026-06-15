"""Tests for LED output adapters."""

from __future__ import annotations

from toxic_game.engine.led_frames import build_frame
from toxic_game.hw.led_output import (
    NoOpLedOutput,
    SimLedOutput,
    build_driver_pixels,
)


def test_sim_led_output_records_frames() -> None:
    output = SimLedOutput()
    frame = build_frame(((255, 0, 0), (0, 255, 0)))

    output.write_frame(frame)

    assert output.frames == [((255, 0, 0), (0, 255, 0))]


def test_noop_led_output_does_not_raise() -> None:
    output = NoOpLedOutput()
    output.write_frame(build_frame(((1, 2, 3),)))


def test_build_driver_pixels_prefixes_muted_rgbw_segment() -> None:
    frame = build_frame(((255, 0, 0), (0, 255, 0), (1, 2, 3)))

    driver = build_driver_pixels(frame, muted_rgbw_count=3, rgbw_count=2)

    assert driver == (
        (0, 0, 0),
        (0, 0, 0),
        (0, 0, 0),
        (255, 0, 0),
        (0, 255, 0),
    )


def test_build_driver_pixels_without_muted_prefix() -> None:
    frame = build_frame(((255, 0, 0), (0, 255, 0)))

    driver = build_driver_pixels(frame, muted_rgbw_count=0, rgbw_count=2)

    assert driver == ((255, 0, 0), (0, 255, 0))
