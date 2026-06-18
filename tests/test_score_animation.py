"""Tests for the end-of-song score reveal animation."""

from __future__ import annotations

from toxic_game.engine.led_frames import CYAN, MAGENTA, OFF
from toxic_game.engine.score_animation import (
    build_score_frame,
    leds_to_light,
    run_score_animation,
    score_percentage,
)
from toxic_game.hw.led_output import SimLedOutput
from toxic_game.hw.sfx import RecordingSfxPlayer


def test_score_percentage_zero_when_no_notes() -> None:
    assert (
        score_percentage(
            perfect=0,
            good=0,
            total_notes=0,
            score_perfect=3,
            score_good=1,
        )
        == 0
    )


def test_score_percentage_caps_at_100() -> None:
    pct = score_percentage(
        perfect=2,
        good=0,
        total_notes=2,
        score_perfect=3,
        score_good=1,
    )
    assert pct == 100


def test_score_percentage_partial() -> None:
    pct = score_percentage(
        perfect=0,
        good=1,
        total_notes=2,
        score_perfect=3,
        score_good=1,
    )
    assert pct == 50


def test_leds_to_light_rounds() -> None:
    assert leds_to_light(0, 10) == 0
    assert leds_to_light(50, 10) == 5
    assert leds_to_light(100, 10) == 10


def test_build_score_frame_fills_from_outside() -> None:
    frame = build_score_frame(strip_len=20, p1_leds=3, p2_leds=2)

    assert frame.pixels[0] == MAGENTA
    assert frame.pixels[1] == MAGENTA
    assert frame.pixels[2] == MAGENTA
    assert frame.pixels[3] == OFF
    assert frame.pixels[19] == CYAN
    assert frame.pixels[18] == CYAN
    assert frame.pixels[17] == OFF


def test_run_score_animation_steps_and_chimes() -> None:
    led = SimLedOutput()
    sfx = RecordingSfxPlayer()
    delays: list[float] = []

    run_score_animation(
        led_output=led,
        sfx=sfx,
        strip_len=20,
        p1_target=2,
        p2_target=3,
        step_ms=200,
        sleep=delays.append,
    )

    assert len(led.frames) == 3  # max(2, 3) steps
    assert sfx.events == ["chime", "chime", "chime"]
    assert delays == [0.2, 0.2, 0.2]

    final = led.frames[-1]
    assert final[0] == MAGENTA
    assert final[1] == MAGENTA
    assert final[2] == OFF  # p1 capped at 2
    assert final[19] == CYAN
    assert final[18] == CYAN
    assert final[17] == CYAN


def test_run_score_animation_no_score_does_nothing() -> None:
    led = SimLedOutput()
    sfx = RecordingSfxPlayer()

    run_score_animation(
        led_output=led,
        sfx=sfx,
        strip_len=20,
        p1_target=0,
        p2_target=0,
        step_ms=200,
        sleep=lambda _: None,
    )

    assert led.frames == []
    assert sfx.events == []
