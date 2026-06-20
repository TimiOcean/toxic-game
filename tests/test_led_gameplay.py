"""Tests for gameplay LED projection."""

from __future__ import annotations

from toxic_game.config import LedConfig
from toxic_game.engine.led_frames import CYAN, GOLD, MAGENTA, OFF, RED, WHITE, scale_pixel
from toxic_game.engine.led_gameplay import (
    HitFeedback,
    build_gameplay_frame,
    center_spawn_head_index,
    hit_marker_range,
)
from toxic_game.engine.notes import ResolvedNote
from toxic_game.engine.scoring import Judgement


def _p1_note(*, hit_ms: int, spawn_ms: int) -> ResolvedNote:
    return ResolvedNote(player=1, bar=1, beat=1, hit_ms=hit_ms, spawn_ms=spawn_ms)


def _p2_note(*, hit_ms: int, spawn_ms: int) -> ResolvedNote:
    return ResolvedNote(player=2, bar=1, beat=1, hit_ms=hit_ms, spawn_ms=spawn_ms)


def _led_config(**overrides: object) -> LedConfig:
    defaults = {
        "muted_rgb_count": 0,
        "rgbw_count": 10,
        "pin": 18,
        "freq_hz": 800000,
        "dma": 10,
        "invert": False,
        "brightness": 255,
        "channel": 0,
        "hit_flash_ms": 500,
        "running_light_span": 4,
        "rgbw_byte_order": "WRGB",
        "hit_marker_fraction": 0.10,
        "running_light_spawn": "end",
    }
    defaults.update(overrides)
    return LedConfig(**defaults)  # type: ignore[arg-type]


def _frame(**kwargs: object):
    defaults = {
        "strip_len": 10,
        "span": 4,
        "progress_ms": 0,
        "notes": (),
        "feedback": (),
        "led": _led_config(),
    }
    defaults.update(kwargs)
    return build_gameplay_frame(**defaults)  # type: ignore[arg-type]


def test_static_markers_hidden_during_hit_feedback() -> None:
    p1_start, p1_end = hit_marker_range(player=1, strip_len=10, span=4, fraction=0.10)
    frame = _frame(
        progress_ms=1050,
        feedback=(HitFeedback(player=1, started_ms=1000, judgement=Judgement.PERFECT),),
    )

    for index in range(p1_start, p1_end + 1):
        assert frame.pixels[index] != scale_pixel(MAGENTA, 0.60)


def test_static_markers_always_visible() -> None:
    frame = _frame()

    p1_start, p1_end = hit_marker_range(player=1, strip_len=10, span=4, fraction=0.10)
    p2_start, p2_end = hit_marker_range(player=2, strip_len=10, span=4, fraction=0.10)
    dim_magenta = scale_pixel(MAGENTA, 0.60)
    dim_cyan = scale_pixel(CYAN, 0.60)

    for index in range(p1_start, p1_end + 1):
        assert frame.pixels[index] == dim_magenta
    for index in range(p2_start, p2_end + 1):
        assert frame.pixels[index] == dim_cyan


def test_running_light_overlays_marker_at_hit() -> None:
    note = _p1_note(hit_ms=1000, spawn_ms=0)
    frame = _frame(progress_ms=1000, notes=(note,))

    marker_start, marker_end = hit_marker_range(player=1, strip_len=10, span=4, fraction=0.10)
    for index in range(marker_start, marker_end + 1):
        assert frame.pixels[index] != OFF
        assert sum(frame.pixels[index]) >= sum(scale_pixel(MAGENTA, 0.60))


def test_running_light_hidden_after_hit() -> None:
    frame = _frame(progress_ms=1001, notes=(_p1_note(hit_ms=1000, spawn_ms=0),))

    marker_start, marker_end = hit_marker_range(player=1, strip_len=10, span=4, fraction=0.10)
    dim_magenta = scale_pixel(MAGENTA, 0.60)
    for index in range(marker_start, marker_end + 1):
        assert frame.pixels[index] == dim_magenta


def test_running_light_keeps_constant_intensity() -> None:
    note = _p1_note(hit_ms=3000, spawn_ms=0)
    early = _frame(progress_ms=800, notes=(note,))
    late = _frame(progress_ms=2000, notes=(note,))
    assert max(sum(pixel) for pixel in early.pixels) == max(sum(pixel) for pixel in late.pixels)


def test_p1_travel_starts_on_right_end() -> None:
    frame = _frame(notes=(_p1_note(hit_ms=1000, spawn_ms=0),))
    assert frame.pixels[-1] != OFF

    early_travel = _frame(progress_ms=200, notes=(_p1_note(hit_ms=1000, spawn_ms=0),))
    assert any(pixel != OFF for pixel in early_travel.pixels)


def test_p2_travel_starts_on_left_end() -> None:
    frame = _frame(notes=(_p2_note(hit_ms=1000, spawn_ms=0),))
    assert frame.pixels[0] != OFF

    early_travel = _frame(progress_ms=200, notes=(_p2_note(hit_ms=1000, spawn_ms=0),))
    assert any(pixel != OFF for pixel in early_travel.pixels)


def test_p1_keeps_constant_brightness_toward_hit() -> None:
    early = _frame(progress_ms=0, span=1, notes=(_p1_note(hit_ms=1000, spawn_ms=0),))
    late = _frame(progress_ms=900, span=1, notes=(_p1_note(hit_ms=1000, spawn_ms=0),))

    early_peak = max(sum(pixel) for pixel in early.pixels)
    late_peak = max(sum(pixel) for pixel in late.pixels)
    assert late_peak == early_peak


def test_center_spawn_p1_starts_at_middle_not_right_end() -> None:
    note = _p1_note(hit_ms=1000, spawn_ms=0)
    led = _led_config(running_light_spawn="center")
    strip_len = 20
    span = 4
    spawn_head = center_spawn_head_index(strip_len=strip_len, span=span, player=1)
    frame = _frame(strip_len=strip_len, span=span, notes=(note,), led=led)

    assert frame.pixels[-1] == OFF
    assert frame.pixels[spawn_head] != OFF

    mid_travel = _frame(
        progress_ms=500,
        strip_len=strip_len,
        span=span,
        notes=(note,),
        led=led,
    )
    assert mid_travel.pixels[-1] == OFF
    left_half = mid_travel.pixels[: strip_len // 2]
    assert any(pixel != OFF for pixel in left_half)
    assert all(pixel == OFF or sum(pixel) <= sum(MAGENTA) for pixel in left_half)


def test_center_spawn_p1_reaches_marker_at_hit() -> None:
    note = _p1_note(hit_ms=1000, spawn_ms=0)
    frame = _frame(
        progress_ms=1000,
        notes=(note,),
        led=_led_config(running_light_spawn="center"),
    )

    marker_start, marker_end = hit_marker_range(player=1, strip_len=10, span=4, fraction=0.10)
    for index in range(marker_start, marker_end + 1):
        assert frame.pixels[index] != OFF
        assert sum(frame.pixels[index]) >= sum(scale_pixel(MAGENTA, 0.60))


def test_center_spawn_p2_starts_at_middle_not_left_end() -> None:
    note = _p2_note(hit_ms=1000, spawn_ms=0)
    led = _led_config(running_light_spawn="center")
    spawn_head = center_spawn_head_index(strip_len=10, span=4, player=2)
    mid_travel = _frame(progress_ms=500, notes=(note,), led=led)

    assert mid_travel.pixels[0] == OFF
    assert mid_travel.pixels[spawn_head] != OFF


def test_center_spawn_head_index_centers_the_span() -> None:
    assert center_spawn_head_index(strip_len=10, span=4, player=1) == 6
    assert center_spawn_head_index(strip_len=10, span=4, player=2) == 3


def test_perfect_feedback_is_white_burst() -> None:
    frame = _frame(
        strip_len=20,
        progress_ms=1050,
        feedback=(HitFeedback(player=1, started_ms=1000, judgement=Judgement.PERFECT),),
    )

    assert frame.pixels[0] == WHITE


def test_error_feedback_starts_at_full_size() -> None:
    frame_start = _frame(
        strip_len=20,
        progress_ms=1000,
        feedback=(HitFeedback(player=2, started_ms=1000, judgement=Judgement.ERROR),),
        led=_led_config(hit_flash_ms=500),
    )
    frame_mid = _frame(
        strip_len=20,
        progress_ms=1250,
        feedback=(HitFeedback(player=2, started_ms=1000, judgement=Judgement.ERROR),),
        led=_led_config(hit_flash_ms=500),
    )

    lit_start = sum(1 for pixel in frame_start.pixels if pixel != OFF)
    lit_mid = sum(1 for pixel in frame_mid.pixels if pixel != OFF)
    assert lit_start >= lit_mid
    assert frame_start.pixels[-1] == RED


def test_error_feedback_is_red_burst() -> None:
    frame = _frame(
        strip_len=20,
        progress_ms=1050,
        feedback=(HitFeedback(player=2, started_ms=1000, judgement=Judgement.ERROR),),
    )

    assert frame.pixels[-1] == RED


def test_good_feedback_is_solid_gold() -> None:
    frame = _frame(
        strip_len=20,
        progress_ms=1090,
        feedback=(HitFeedback(player=1, started_ms=1000, judgement=Judgement.GOOD),),
    )

    assert frame.pixels[0] == GOLD


def test_feedback_hidden_after_flash_window() -> None:
    frame = _frame(
        progress_ms=1600,
        feedback=(HitFeedback(player=1, started_ms=1000, judgement=Judgement.PERFECT),),
        led=_led_config(hit_flash_ms=500),
    )

    p1_start, p1_end = hit_marker_range(player=1, strip_len=10, span=4, fraction=0.10)
    dim_magenta = scale_pixel(MAGENTA, 0.60)
    for index in range(p1_start, p1_end + 1):
        assert frame.pixels[index] == dim_magenta
    assert frame.pixels[0] != WHITE


def test_p1_travel_uses_magenta() -> None:
    frame = _frame(progress_ms=500, span=1, notes=(_p1_note(hit_ms=1000, spawn_ms=0),))
    lit = next(color for color in frame.pixels if color != OFF and color != scale_pixel(CYAN, 0.60))

    assert lit == MAGENTA or lit[0] > 0 and lit[2] > 0
