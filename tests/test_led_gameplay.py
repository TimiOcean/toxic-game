"""Tests for gameplay LED projection."""

from __future__ import annotations

from toxic_game.engine.led_frames import MAGENTA, OFF, RED, WHITE
from toxic_game.engine.led_gameplay import HitFeedback, build_gameplay_frame
from toxic_game.engine.notes import ResolvedNote
from toxic_game.engine.scoring import Judgement


def _p1_note(*, hit_ms: int, spawn_ms: int) -> ResolvedNote:
    return ResolvedNote(player=1, bar=1, beat=1, hit_ms=hit_ms, spawn_ms=spawn_ms)


def _p2_note(*, hit_ms: int, spawn_ms: int) -> ResolvedNote:
    return ResolvedNote(player=2, bar=1, beat=1, hit_ms=hit_ms, spawn_ms=spawn_ms)


def _frame(**kwargs: object):
    defaults = {
        "strip_len": 10,
        "span": 4,
        "progress_ms": 0,
        "notes": (),
        "feedback": (),
        "hit_flash_ms": 180,
    }
    defaults.update(kwargs)
    return build_gameplay_frame(**defaults)  # type: ignore[arg-type]


def test_p1_travel_starts_on_right_end() -> None:
    frame = _frame(notes=(_p1_note(hit_ms=1000, spawn_ms=0),))

    assert frame.pixels[-1] != OFF
    assert frame.pixels[0] == OFF


def test_p1_travel_ends_on_left_end() -> None:
    frame = _frame(progress_ms=999, notes=(_p1_note(hit_ms=1000, spawn_ms=0),))

    assert frame.pixels[0] != OFF
    assert frame.pixels[-1] == OFF


def test_p2_travel_starts_on_left_end() -> None:
    frame = _frame(notes=(_p2_note(hit_ms=1000, spawn_ms=0),))

    assert frame.pixels[0] != OFF
    assert frame.pixels[-1] == OFF


def test_p2_travel_ends_on_right_end() -> None:
    frame = _frame(progress_ms=999, notes=(_p2_note(hit_ms=1000, spawn_ms=0),))

    assert frame.pixels[-1] != OFF
    assert frame.pixels[0] == OFF


def test_p1_gets_brighter_toward_hit() -> None:
    early = _frame(progress_ms=0, span=1, notes=(_p1_note(hit_ms=1000, spawn_ms=0),))
    late = _frame(progress_ms=900, span=1, notes=(_p1_note(hit_ms=1000, spawn_ms=0),))

    early_peak = max(sum(pixel) for pixel in early.pixels)
    late_peak = max(sum(pixel) for pixel in late.pixels)
    assert late_peak > early_peak


def test_perfect_feedback_is_white_on_left_end() -> None:
    frame = _frame(
        progress_ms=1050,
        feedback=(HitFeedback(player=1, started_ms=1000, judgement=Judgement.PERFECT),),
    )

    assert frame.pixels[0] == WHITE
    assert frame.pixels[-1] == OFF


def test_error_feedback_is_red_on_right_end() -> None:
    frame = _frame(
        progress_ms=1050,
        feedback=(HitFeedback(player=2, started_ms=1000, judgement=Judgement.ERROR),),
    )

    assert frame.pixels[-1] == RED
    assert frame.pixels[0] == OFF


def test_feedback_hidden_after_flash_window() -> None:
    frame = _frame(
        progress_ms=1200,
        feedback=(HitFeedback(player=1, started_ms=1000, judgement=Judgement.PERFECT),),
    )

    assert all(pixel == OFF for pixel in frame.pixels)


def test_p1_travel_uses_magenta() -> None:
    frame = _frame(progress_ms=500, span=1, notes=(_p1_note(hit_ms=1000, spawn_ms=0),))
    lit = next(color for color in frame.pixels if color != OFF)

    assert lit == MAGENTA or lit[0] > 0 and lit[2] > 0
