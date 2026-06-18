"""End-of-song score reveal for the rhythm jump game.

Pure scoring math plus a stepped, synchronized LED reveal: each player's score
percentage maps to a number of LEDs lit from the outside of their half of the
strip inward, lit one at a time with a chime per new LED.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from toxic_game.engine.led_frames import (
    CYAN,
    MAGENTA,
    LedFrame,
    blank_pixels,
    build_frame,
)
from toxic_game.hw.led_output import LedOutput
from toxic_game.hw.sfx import NoOpSfxPlayer, SfxPlayer


def score_percentage(
    *,
    perfect: int,
    good: int,
    total_notes: int,
    score_perfect: int,
    score_good: int,
) -> int:
    """Return the player's score as a percentage capped at 100.

    100% corresponds to hitting every note with at least a good judgement.
    """
    if total_notes <= 0:
        return 0
    raw = score_perfect * perfect + score_good * good
    return min(100, round(100 * raw / total_notes))


def leds_to_light(pct: int, half_len: int) -> int:
    """Return how many LEDs in a half should light for ``pct`` percent."""
    return round(pct / 100 * half_len)


def build_score_frame(*, strip_len: int, p1_leds: int, p2_leds: int) -> LedFrame:
    """Fill the left half magenta and the right half cyan from the outside in."""
    pixels = blank_pixels(strip_len)
    for offset in range(min(p1_leds, strip_len)):
        pixels[offset] = MAGENTA
    for offset in range(min(p2_leds, strip_len)):
        pixels[strip_len - 1 - offset] = CYAN
    return build_frame(pixels)


def run_score_animation(
    *,
    led_output: LedOutput,
    sfx: SfxPlayer | None = None,
    strip_len: int,
    p1_target: int,
    p2_target: int,
    step_ms: int,
    sleep: Callable[[float], None] | None = None,
) -> None:
    """Reveal both players' scores one synchronized LED per step.

    A ``chime`` plays for each new LED that lights up. ``sleep`` is injectable
    for tests.
    """
    sfx = sfx or NoOpSfxPlayer()
    sleep = sleep or time.sleep
    total_steps = max(p1_target, p2_target)
    for step in range(1, total_steps + 1):
        p1_leds = min(step, p1_target)
        p2_leds = min(step, p2_target)
        led_output.write_frame(
            build_score_frame(
                strip_len=strip_len,
                p1_leds=p1_leds,
                p2_leds=p2_leds,
            ),
        )
        sfx.play("chime")
        sleep(step_ms / 1000)
