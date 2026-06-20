"""Tests for the LED check CLI."""

from __future__ import annotations

from toxic_game.config import build_led_config
from toxic_game.hw.led_output import SimLedOutput
from toxic_game.hw.led_patterns import solid_pixels
from toxic_game.tools.led_check import LedCheckOptions, run_led_check


def test_run_led_check_clears_strip_at_end() -> None:
    output = SimLedOutput()

    run_led_check(
        options=LedCheckOptions(
            pattern="solid",
            color_name="red",
            side="left",
            repeat=1,
            delay_s=0.0,
        ),
        writer=output,
        sleep=lambda _seconds: None,
        stdout=lambda _message: None,
    )

    strip_len = build_led_config().active_count
    assert len(output.frames) == 2
    assert output.frames[-1] == solid_pixels(strip_len, (0, 0, 0))
