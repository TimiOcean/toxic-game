"""Tests for pad presence tracking."""

from __future__ import annotations

from toxic_game.engine.presence import (
    EmptyShutdownTracker,
    HeldStates,
    HoldStartTracker,
)


def test_hold_start_ignores_brief_pulse() -> None:
    tracker = HoldStartTracker(start_hold_ms=500)
    assert tracker.update(HeldStates(p1=True, p2=False), now_ms=0) is None
    assert tracker.update(HeldStates(p1=False, p2=False), now_ms=200) is None
    assert tracker.update(HeldStates(p1=True, p2=False), now_ms=300) is None
    assert tracker.update(HeldStates(p1=False, p2=False), now_ms=400) is None


def test_hold_start_fires_after_required_duration() -> None:
    tracker = HoldStartTracker(start_hold_ms=500)
    assert tracker.update(HeldStates(p1=True, p2=False), now_ms=0) is None
    assert tracker.update(HeldStates(p1=True, p2=False), now_ms=499) is None
    assert tracker.update(HeldStates(p1=True, p2=False), now_ms=500) == 1


def test_hold_start_does_not_repeat_while_still_held() -> None:
    tracker = HoldStartTracker(start_hold_ms=500)
    tracker.update(HeldStates(p1=True, p2=False), now_ms=500)
    assert tracker.update(HeldStates(p1=True, p2=False), now_ms=900) is None


def test_hold_start_resets_on_release() -> None:
    tracker = HoldStartTracker(start_hold_ms=500)
    tracker.update(HeldStates(p1=True, p2=False), now_ms=500)
    tracker.update(HeldStates(p1=False, p2=False), now_ms=600)
    assert tracker.update(HeldStates(p1=True, p2=False), now_ms=700) is None
    assert tracker.update(HeldStates(p1=True, p2=False), now_ms=1200) == 1


def test_hold_start_p1_priority_when_both_qualify() -> None:
    tracker = HoldStartTracker(start_hold_ms=500)
    tracker.update(HeldStates(p1=True, p2=True), now_ms=0)
    assert tracker.update(HeldStates(p1=True, p2=True), now_ms=500) == 1


def test_empty_shutdown_requires_both_pads_open() -> None:
    tracker = EmptyShutdownTracker(threshold_ms=5000)
    assert tracker.update(HeldStates(p1=True, p2=False), now_ms=0) is False
    assert tracker.update(HeldStates(p1=False, p2=True), now_ms=1000) is False
    assert tracker.update(HeldStates(p1=False, p2=False), now_ms=2000) is False
    assert tracker.update(HeldStates(p1=False, p2=False), now_ms=6999) is False
    assert tracker.update(HeldStates(p1=False, p2=False), now_ms=7000) is True


def test_empty_shutdown_resets_when_either_pad_held() -> None:
    tracker = EmptyShutdownTracker(threshold_ms=5000)
    tracker.update(HeldStates(p1=False, p2=False), now_ms=0)
    tracker.update(HeldStates(p1=False, p2=False), now_ms=4000)
    assert tracker.update(HeldStates(p1=True, p2=False), now_ms=4500) is False
    assert tracker.update(HeldStates(p1=False, p2=False), now_ms=5000) is False
    assert tracker.update(HeldStates(p1=False, p2=False), now_ms=9999) is False
    assert tracker.update(HeldStates(p1=False, p2=False), now_ms=10000) is True
