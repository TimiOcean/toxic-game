"""Tests for gameplay scoring judgements."""

from __future__ import annotations

from typing import Literal

from toxic_game.config import JudgementWindowsMs
from toxic_game.engine.notes import ResolvedNote
from toxic_game.engine.scoring import Judgement, evaluate_press, pop_missed_notes


def _note(*, player: Literal[1, 2], hit_ms: int) -> ResolvedNote:
    return ResolvedNote(
        player=player,
        bar=1,
        beat=1,
        hit_ms=hit_ms,
        spawn_ms=max(hit_ms - 1000, 0),
    )


def test_perfect_boundary_is_inclusive() -> None:
    windows = JudgementWindowsMs(perfect=20, good=50)
    notes = (_note(player=1, hit_ms=1000),)

    result = evaluate_press(notes=notes, press_ms=1020, windows=windows)

    assert result.judgement == Judgement.PERFECT
    assert result.matched_note == notes[0]


def test_good_boundary_is_inclusive() -> None:
    windows = JudgementWindowsMs(perfect=20, good=50)
    notes = (_note(player=1, hit_ms=1000),)

    result = evaluate_press(notes=notes, press_ms=1050, windows=windows)

    assert result.judgement == Judgement.GOOD
    assert result.matched_note == notes[0]


def test_press_outside_good_is_error() -> None:
    windows = JudgementWindowsMs(perfect=20, good=50)
    notes = (_note(player=1, hit_ms=1000),)

    result = evaluate_press(notes=notes, press_ms=1051, windows=windows)

    assert result.judgement == Judgement.ERROR
    assert result.matched_note is None


def test_ghost_tap_is_ignored() -> None:
    windows = JudgementWindowsMs(perfect=20, good=50)

    result = evaluate_press(notes=(), press_ms=800, windows=windows)

    assert result.judgement is None
    assert result.matched_note is None


def test_evaluation_uses_nearest_note() -> None:
    windows = JudgementWindowsMs(perfect=20, good=50)
    near = _note(player=1, hit_ms=1000)
    far = _note(player=1, hit_ms=1300)

    result = evaluate_press(notes=(far, near), press_ms=1010, windows=windows)

    assert result.judgement == Judgement.PERFECT
    assert result.matched_note == near


def test_same_beat_can_be_judged_independently_per_player() -> None:
    windows = JudgementWindowsMs(perfect=20, good=50)
    p1_notes = (_note(player=1, hit_ms=1000),)
    p2_notes = (_note(player=2, hit_ms=1000),)

    p1_result = evaluate_press(notes=p1_notes, press_ms=1005, windows=windows)
    p2_result = evaluate_press(notes=p2_notes, press_ms=1045, windows=windows)

    assert p1_result.judgement == Judgement.PERFECT
    assert p2_result.judgement == Judgement.GOOD


def test_pop_missed_notes_marks_passed_notes_as_missed() -> None:
    windows = JudgementWindowsMs(perfect=20, good=50)
    old_note = _note(player=1, hit_ms=1000)
    future_note = _note(player=1, hit_ms=1200)

    active, missed = pop_missed_notes(
        notes=(old_note, future_note),
        now_ms=1051,
        windows=windows,
    )

    assert missed == (old_note,)
    assert active == (future_note,)
