"""Pad presence helpers for arcade hold-to-start and in-game empty shutdown."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

PlayerId = Literal[1, 2]


@dataclass(frozen=True, slots=True)
class HeldStates:
    """Raw contact state: ``True`` when the pad/button circuit is closed."""

    p1: bool
    p2: bool


@dataclass(slots=True)
class _SideHoldState:
    hold_started_ms: int | None = None
    fired: bool = False


@dataclass(slots=True)
class HoldStartTracker:
    """Detect sustained pad contact for arcade game selection."""

    start_hold_ms: int
    _p1: _SideHoldState = field(default_factory=_SideHoldState)
    _p2: _SideHoldState = field(default_factory=_SideHoldState)

    def update(self, held: HeldStates, *, now_ms: int) -> PlayerId | None:
        """Return 1 or 2 when that side has been held long enough, else ``None``."""
        p1_ready = self._update_side(self._p1, held.p1, now_ms=now_ms)
        p2_ready = self._update_side(self._p2, held.p2, now_ms=now_ms)
        if p1_ready:
            return 1
        if p2_ready:
            return 2
        return None

    def _update_side(
        self,
        state: _SideHoldState,
        connected: bool,
        *,
        now_ms: int,
    ) -> bool:
        if connected:
            if state.hold_started_ms is None:
                state.hold_started_ms = now_ms
            if (
                not state.fired
                and now_ms - state.hold_started_ms >= self.start_hold_ms
            ):
                state.fired = True
                return True
            return False
        state.hold_started_ms = None
        state.fired = False
        return False


@dataclass(slots=True)
class EmptyShutdownTracker:
    """Detect when both pads have been empty long enough to abandon a game."""

    threshold_ms: int
    _empty_since_ms: int | None = None

    def update(self, held: HeldStates, *, now_ms: int) -> bool:
        """Return ``True`` once both pads have been open for ``threshold_ms``."""
        if held.p1 or held.p2:
            self._empty_since_ms = None
            return False
        if self._empty_since_ms is None:
            self._empty_since_ms = now_ms
            return False
        return (now_ms - self._empty_since_ms) >= self.threshold_ms
