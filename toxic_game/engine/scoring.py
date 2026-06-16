"""Judgement helpers for press timing and misses."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from toxic_game.config import JudgementWindowsMs
from toxic_game.engine.notes import ResolvedNote


class Judgement(StrEnum):
    """Possible scoring outcomes."""

    PERFECT = "perfect"
    GOOD = "good"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class PressEvaluation:
    """Outcome of evaluating one player press."""

    judgement: Judgement | None
    matched_note: ResolvedNote | None


def _nearest_note(notes: tuple[ResolvedNote, ...], press_ms: int) -> ResolvedNote | None:
    if not notes:
        return None
    return min(notes, key=lambda note: abs(note.hit_ms - press_ms))


def evaluate_press(
    *,
    notes: tuple[ResolvedNote, ...],
    press_ms: int,
    windows: JudgementWindowsMs,
) -> PressEvaluation:
    """Evaluate one press against a player's pending notes.

    Ghost taps are ignored (``judgement`` and ``matched_note`` are both ``None``).
    """
    nearest = _nearest_note(notes, press_ms)
    if nearest is None:
        return PressEvaluation(judgement=None, matched_note=None)

    delta_ms = abs(press_ms - nearest.hit_ms)
    if delta_ms <= windows.perfect:
        return PressEvaluation(judgement=Judgement.PERFECT, matched_note=nearest)
    if delta_ms <= windows.good:
        return PressEvaluation(judgement=Judgement.GOOD, matched_note=nearest)
    return PressEvaluation(judgement=Judgement.ERROR, matched_note=None)


def pop_missed_notes(
    *,
    notes: tuple[ResolvedNote, ...],
    now_ms: int,
    windows: JudgementWindowsMs,
) -> tuple[tuple[ResolvedNote, ...], tuple[ResolvedNote, ...]]:
    """Split pending notes into active and missed at ``now_ms``."""
    cutoff = now_ms - windows.good
    missed: list[ResolvedNote] = []
    active: list[ResolvedNote] = []
    for note in notes:
        if note.hit_ms < cutoff:
            missed.append(note)
        else:
            active.append(note)
    return tuple(active), tuple(missed)
