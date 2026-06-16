"""Tests for gameplay LED projection."""

from __future__ import annotations

from toxic_game.engine.led_frames import MAGENTA, OFF, RED, WHITE
from toxic_game.engine.led_gameplay import build_gameplay_frame
from toxic_game.engine.notes import ResolvedNote


def _p1_note(*, hit_ms: int, spawn_ms: int) -> ResolvedNote:
    return ResolvedNote(player=1, bar=1, beat=1, hit_ms=hit_ms, spawn_ms=spawn_ms)


def _p2_note(*, hit_ms: int, spawn_ms: int) -> ResolvedNote:
    return ResolvedNote(player=2, bar=1, beat=1, hit_ms=hit_ms, spawn_ms=spawn_ms)


def test_p1_travel_starts_on_right_end() -> None:
    frame = build_gameplay_frame(
        strip_len=10,
        span=4,
        progress_ms=0,
        notes=(_p1_note(hit_ms=1000, spawn_ms=0),),
        hit_flash_ms=180,
    )

    assert frame.pixels[-1] != OFF
    assert frame.pixels[0] == OFF


def test_p1_travel_ends_on_left_end() -> None:
    frame = build_gameplay_frame(
        strip_len=10,
        span=4,
        progress_ms=999,
        notes=(_p1_note(hit_ms=1000, spawn_ms=0),),
        hit_flash_ms=180,
    )

    assert frame.pixels[0] != OFF
    assert frame.pixels[-1] == OFF


def test_p2_travel_starts_on_left_end() -> None:
    frame = build_gameplay_frame(
        strip_len=10,
        span=4,
        progress_ms=0,
        notes=(_p2_note(hit_ms=1000, spawn_ms=0),),
        hit_flash_ms=180,
    )

    assert frame.pixels[0] != OFF
    assert frame.pixels[-1] == OFF


def test_p2_travel_ends_on_right_end() -> None:
    frame = build_gameplay_frame(
        strip_len=10,
        span=4,
        progress_ms=999,
        notes=(_p2_note(hit_ms=1000, spawn_ms=0),),
        hit_flash_ms=180,
    )

    assert frame.pixels[-1] != OFF
    assert frame.pixels[0] == OFF


def test_p1_gets_brighter_toward_hit() -> None:
    early = build_gameplay_frame(
        strip_len=10,
        span=1,
        progress_ms=0,
        notes=(_p1_note(hit_ms=1000, spawn_ms=0),),
        hit_flash_ms=180,
    )
    late = build_gameplay_frame(
        strip_len=10,
        span=1,
        progress_ms=900,
        notes=(_p1_note(hit_ms=1000, spawn_ms=0),),
        hit_flash_ms=180,
    )

    early_peak = max(sum(pixel) for pixel in early.pixels)
    late_peak = max(sum(pixel) for pixel in late.pixels)
    assert late_peak > early_peak


def test_p1_flash_is_white_on_left_end() -> None:
    frame = build_gameplay_frame(
        strip_len=10,
        span=4,
        progress_ms=1050,
        notes=(_p1_note(hit_ms=1000, spawn_ms=0),),
        hit_flash_ms=180,
    )

    assert frame.pixels[0] == WHITE
    assert frame.pixels[-1] == OFF


def test_p2_flash_is_red_on_right_end() -> None:
    frame = build_gameplay_frame(
        strip_len=10,
        span=4,
        progress_ms=1050,
        notes=(_p2_note(hit_ms=1000, spawn_ms=0),),
        hit_flash_ms=180,
    )

    assert frame.pixels[-1] == RED
    assert frame.pixels[0] == OFF


def test_note_hidden_before_spawn_and_after_flash() -> None:
    note = _p1_note(hit_ms=1000, spawn_ms=500)
    before = build_gameplay_frame(
        strip_len=10,
        span=4,
        progress_ms=400,
        notes=(note,),
        hit_flash_ms=180,
    )
    after = build_gameplay_frame(
        strip_len=10,
        span=4,
        progress_ms=1200,
        notes=(note,),
        hit_flash_ms=180,
    )

    assert all(pixel == OFF for pixel in before.pixels)
    assert all(pixel == OFF for pixel in after.pixels)


def test_p1_travel_uses_magenta() -> None:
    frame = build_gameplay_frame(
        strip_len=10,
        span=1,
        progress_ms=500,
        notes=(_p1_note(hit_ms=1000, spawn_ms=0),),
        hit_flash_ms=180,
    )
    lit = next(color for color in frame.pixels if color != OFF)

    assert lit == MAGENTA or lit[0] > 0 and lit[2] > 0
