"""End-of-song score reveal and applause animations.

Pure scoring math plus a stepped, synchronized LED reveal: each player's score
percentage maps to a number of LEDs lit from the outside of their half of the
strip inward, lit one at a time (or in segments) with a chime per step.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Literal

from toxic_game.engine.led_frames import (
    CYAN,
    MAGENTA,
    LedFrame,
    OFF,
    RgbPixel,
    blank_pixels,
    build_frame,
)
from toxic_game.hw.led_output import LedOutput
from toxic_game.hw.sfx import NoOpSfxPlayer, SfxPlayer

PlayerSide = Literal[1, 2]


def score_percentage(
    *,
    perfect: int,
    good: int,
    total_notes: int,
    score_perfect: int,
    score_good: int,
) -> int:
    """Return the player's score as a percentage capped at 100.

    100% corresponds to hitting every note with a perfect judgement.
    """
    if total_notes <= 0 or score_perfect <= 0:
        return 0
    raw = score_perfect * perfect + score_good * good
    max_raw = total_notes * score_perfect
    return min(100, round(100 * raw / max_raw))


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


def build_half_flash_frame(
    *,
    strip_len: int,
    color: RgbPixel,
    side: PlayerSide,
) -> LedFrame:
    """Return a frame with only one half lit in ``color``."""
    pixels = blank_pixels(strip_len)
    half_len = strip_len // 2
    if side == 1:
        for index in range(half_len):
            pixels[index] = color
    else:
        for index in range(strip_len - half_len, strip_len):
            pixels[index] = color
    return build_frame(pixels)


def build_full_flash_frame(*, strip_len: int, color: RgbPixel) -> LedFrame:
    """Return a frame with every gameplay LED set to ``color``."""
    return build_frame([color for _ in range(strip_len)])


def build_tie_applause_frame(*, strip_len: int) -> LedFrame:
    """Return a frame with magenta left half and cyan right half."""
    return build_score_frame(strip_len=strip_len, p1_leds=strip_len // 2, p2_leds=strip_len // 2)


def run_score_animation(
    *,
    led_output: LedOutput,
    sfx: SfxPlayer | None = None,
    strip_len: int,
    p1_target: int,
    p2_target: int,
    step_ms: int,
    step_leds: int = 1,
    sleep: Callable[[float], None] | None = None,
) -> None:
    """Reveal both players' scores in synchronized steps.

    Each step lights ``step_leds`` more LEDs per half (outside-in). A ``chime``
    plays per step. ``sleep`` is injectable for tests.
    """
    sfx = sfx or NoOpSfxPlayer()
    sleep = sleep or time.sleep
    step_leds = max(1, step_leds)
    total_steps = max(
        (p1_target + step_leds - 1) // step_leds,
        (p2_target + step_leds - 1) // step_leds,
    )
    for step in range(1, total_steps + 1):
        p1_leds = min(step * step_leds, p1_target)
        p2_leds = min(step * step_leds, p2_target)
        led_output.write_frame(
            build_score_frame(
                strip_len=strip_len,
                p1_leds=p1_leds,
                p2_leds=p2_leds,
            ),
        )
        sfx.play("chime")
        sleep(step_ms / 1000)


def run_applause_animation(
    *,
    led_output: LedOutput,
    sfx: SfxPlayer | None = None,
    on_frame: LedFrame,
    count: int,
    flash_ms: int,
    sleep: Callable[[float], None] | None = None,
) -> None:
    """Play applause once, then flash ``on_frame`` on/off ``count`` times."""
    sfx = sfx or NoOpSfxPlayer()
    sleep = sleep or time.sleep
    off_frame = build_frame(blank_pixels(len(on_frame.pixels)))
    sfx.play("applause")
    for _ in range(count):
        led_output.write_frame(on_frame)
        sleep(flash_ms / 1000)
        led_output.write_frame(off_frame)
        sleep(flash_ms / 1000)


__all__ = [
    "PlayerSide",
    "build_full_flash_frame",
    "build_half_flash_frame",
    "build_score_frame",
    "build_tie_applause_frame",
    "leds_to_light",
    "run_applause_animation",
    "run_score_animation",
    "score_percentage",
]
