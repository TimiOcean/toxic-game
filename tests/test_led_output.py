"""Tests for LED output adapters."""

from __future__ import annotations

from toxic_game.engine.led_frames import build_frame
from toxic_game.hw.led_output import NoOpLedOutput, SimLedOutput, map_logical_frame_to_physical


def test_sim_led_output_records_frames() -> None:
    output = SimLedOutput()
    frame = build_frame(((255, 0, 0), (0, 255, 0)))

    output.write_frame(frame)

    assert output.frames == [((255, 0, 0), (0, 255, 0))]


def test_noop_led_output_does_not_raise() -> None:
    output = NoOpLedOutput()
    output.write_frame(build_frame(((1, 2, 3),)))


def test_map_logical_frame_returns_active_segment_only() -> None:
    frame = build_frame(((255, 0, 0), (0, 255, 0), (1, 2, 3)))

    active = map_logical_frame_to_physical(
        frame,
        muted_rgb_count=10,
        rgbw_count=2,
    )

    assert active == ((255, 0, 0), (0, 255, 0))
