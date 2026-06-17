"""Tests for Pong LED projection."""

from __future__ import annotations

from toxic_game.config import LedConfig
from toxic_game.engine.led_frames import CYAN, MAGENTA, OFF, WHITE, scale_pixel
from toxic_game.engine.led_gameplay import MARKER_INTENSITY, hit_marker_range
from toxic_game.engine.pong_led import ball_index_for_player, build_pong_frame
from toxic_game.engine.scoring import Judgement


def _led_config(**overrides: object) -> LedConfig:
    defaults = {
        "muted_rgb_count": 0,
        "rgbw_count": 30,
        "pin": 18,
        "freq_hz": 800000,
        "dma": 10,
        "invert": False,
        "brightness": 255,
        "channel": 0,
        "hit_flash_ms": 200,
        "running_light_span": 2,
        "rgbw_byte_order": "WRGB",
        "hit_marker_fraction": 0.10,
        "running_light_spawn": "end",
    }
    defaults.update(overrides)
    return LedConfig(**defaults)  # type: ignore[arg-type]


def test_markers_drawn_in_player_colors() -> None:
    led = _led_config()
    frame = build_pong_frame(
        strip_len=30,
        span=2,
        led=led,
        ball_head_index=15,
        ball_color=WHITE,
        ball_visible=False,
        ball_parked=False,
        travel_right_to_left=False,
    )

    p1_start, p1_end = hit_marker_range(player=1, strip_len=30, span=2, fraction=0.10)
    p2_start, p2_end = hit_marker_range(player=2, strip_len=30, span=2, fraction=0.10)
    assert frame.pixels[p1_start] == scale_pixel(MAGENTA, MARKER_INTENSITY)
    assert frame.pixels[p2_end] == scale_pixel(CYAN, MARKER_INTENSITY)


def test_ball_rendered_in_its_color() -> None:
    led = _led_config()
    frame = build_pong_frame(
        strip_len=30,
        span=2,
        led=led,
        ball_head_index=15,
        ball_color=MAGENTA,
        ball_visible=True,
        ball_parked=False,
        travel_right_to_left=True,
    )

    assert frame.pixels[15] == MAGENTA
    assert frame.pixels[14] == MAGENTA


def test_ball_overlaps_marker_at_arrival_index() -> None:
    led = _led_config()
    p2_index = ball_index_for_player(2, strip_len=30, span=2, fraction=0.10)
    frame = build_pong_frame(
        strip_len=30,
        span=2,
        led=led,
        ball_head_index=p2_index,
        ball_color=CYAN,
        ball_visible=True,
        ball_parked=False,
        travel_right_to_left=False,
    )

    p2_start, p2_end = hit_marker_range(player=2, strip_len=30, span=2, fraction=0.10)
    for index in range(p2_start, p2_end + 1):
        assert frame.pixels[index] == CYAN


def test_parked_ball_is_dimmed() -> None:
    led = _led_config()
    frame = build_pong_frame(
        strip_len=30,
        span=2,
        led=led,
        ball_head_index=15,
        ball_color=WHITE,
        ball_visible=True,
        ball_parked=True,
        travel_right_to_left=False,
    )

    assert frame.pixels[15] != OFF
    assert sum(frame.pixels[15]) < sum(WHITE)


def test_feedback_hides_marker_and_flashes_color() -> None:
    led = _led_config()
    frame = build_pong_frame(
        strip_len=30,
        span=2,
        led=led,
        ball_head_index=15,
        ball_color=WHITE,
        ball_visible=False,
        ball_parked=False,
        travel_right_to_left=False,
        feedback=((1, Judgement.PERFECT, 0),),
    )

    assert frame.pixels[0] == WHITE  # perfect flash anchor at P1 end
