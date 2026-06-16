"""Tests for gameplay LED projection."""

from __future__ import annotations

from toxic_game.engine.led_frames import GOLD, MAGENTA, OFF, RED, WHITE
from toxic_game.engine.led_gameplay import HitFeedback, build_gameplay_frame
from toxic_game.engine.notes import ResolvedNote
from toxic_game.engine.scoring import Judgement
from toxic_game.engine.timing import SongTiming


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


def _timing_120() -> SongTiming:
    return SongTiming(bpm=120.0, delay_to_first_beat_ms=500)


def test_running_light_pulses_on_beat() -> None:
    note = _p1_note(hit_ms=3000, spawn_ms=0)
    timing = _timing_120()
    on_beat = _frame(
        progress_ms=1500,
        notes=(note,),
        timing=timing,
    )
    mid_cycle = _frame(
        progress_ms=1250,
        notes=(note,),
        timing=timing,
    )

    on_beat_peak = max(sum(pixel) for pixel in on_beat.pixels)
    mid_cycle_peak = max(sum(pixel) for pixel in mid_cycle.pixels)
    assert on_beat_peak > mid_cycle_peak


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


def test_perfect_feedback_is_sparkling_white() -> None:
    frame = _frame(
        strip_len=20,
        progress_ms=1090,
        feedback=(HitFeedback(player=1, started_ms=1000, judgement=Judgement.PERFECT),),
    )

    # Anchor pixel stays full white.
    assert frame.pixels[0] == WHITE
    # All lit pixels are neutral white (r == g == b), gold is not used.
    for pixel in frame.pixels:
        if pixel != OFF:
            assert pixel[0] == pixel[1] == pixel[2]
    # Sparkle blanks some interior burst pixels, leaving gaps within the span.
    lit_indices = [i for i, pixel in enumerate(frame.pixels) if pixel != OFF]
    span_end = max(lit_indices)
    blanked_within_span = [
        i for i in range(span_end + 1) if frame.pixels[i] == OFF
    ]
    assert blanked_within_span


def test_perfect_flash_is_wider_than_good_at_peak() -> None:
    perfect = _frame(
        strip_len=20,
        progress_ms=1090,
        feedback=(HitFeedback(player=1, started_ms=1000, judgement=Judgement.PERFECT),),
    )
    good = _frame(
        strip_len=20,
        progress_ms=1090,
        feedback=(HitFeedback(player=1, started_ms=1000, judgement=Judgement.GOOD),),
    )

    # Compare reach (span width), since perfect sparkle-blanks some pixels.
    perfect_span = max(i for i, p in enumerate(perfect.pixels) if p != OFF)
    good_span = max(i for i, p in enumerate(good.pixels) if p != OFF)
    assert perfect_span > good_span + 2


def test_error_feedback_is_red_on_right_end() -> None:
    frame = _frame(
        progress_ms=1050,
        feedback=(HitFeedback(player=2, started_ms=1000, judgement=Judgement.ERROR),),
    )

    assert frame.pixels[-1] == RED
    assert frame.pixels[0] == OFF


def test_good_feedback_is_solid_gold() -> None:
    frame = _frame(
        strip_len=20,
        progress_ms=1090,
        feedback=(HitFeedback(player=1, started_ms=1000, judgement=Judgement.GOOD),),
    )

    assert frame.pixels[0] == GOLD
    # No sparkles and no blue channel: every lit pixel is gold-family.
    for pixel in frame.pixels:
        if pixel != OFF:
            assert pixel[2] == 0
            assert pixel[0] > 0 and pixel[1] > 0
    # The burst is contiguous from the hit end (no blanked gaps).
    lit_indices = [i for i, pixel in enumerate(frame.pixels) if pixel != OFF]
    assert lit_indices == list(range(len(lit_indices)))


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
