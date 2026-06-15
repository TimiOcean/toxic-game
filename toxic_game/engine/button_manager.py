"""Button input manager for edge-triggered player presses."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from toxic_game.config import build_gpio_config
from toxic_game.hw.gpio_input import ButtonSide, debounce_accept, read_button_states

_BUTTON_SIDES: tuple[ButtonSide, ...] = ("left", "right")


@dataclass(frozen=True, slots=True)
class ButtonPresses:
    """Edge-triggered presses detected since the previous poll."""

    p1: bool
    p2: bool


class ButtonReader(Protocol):
    """Protocol for objects that return current held button states."""

    def read_states(self) -> dict[ButtonSide, bool]:
        """Return whether each side is currently pressed."""


class CallableButtonReader:
    """Wrap a callable as a :class:`ButtonReader`."""

    def __init__(self, read_states: Callable[[], dict[ButtonSide, bool]]) -> None:
        """Store the state reader."""
        self._read_states = read_states

    def read_states(self) -> dict[ButtonSide, bool]:
        """Return the latest held button states."""
        return self._read_states()


class ButtonManager:
    """Detect rising edges with debounce for P1 (left) and P2 (right)."""

    def __init__(
        self,
        reader: ButtonReader | None = None,
        *,
        debounce_ms: int | None = None,
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        """Configure the manager with a reader and debounce threshold."""
        self._reader = reader or CallableButtonReader(read_button_states)
        gpio_config = build_gpio_config()
        self._debounce_ms = (
            gpio_config.debounce_ms if debounce_ms is None else debounce_ms
        )
        self._clock_ms = clock_ms or (lambda: int(time.monotonic() * 1000))
        self._previous_held = dict.fromkeys(_BUTTON_SIDES, False)
        self._last_accept_ms = dict.fromkeys(_BUTTON_SIDES, 0)

    def poll(self) -> ButtonPresses:
        """Return buttons pressed since the last poll."""
        now_ms = self._clock_ms()
        states = self._reader.read_states()
        p1_pressed = False
        p2_pressed = False

        for side in _BUTTON_SIDES:
            current = bool(states.get(side, False))
            previous = self._previous_held[side]
            rising_edge = current and not previous
            if rising_edge and debounce_accept(
                self._last_accept_ms[side],
                now_ms,
                self._debounce_ms,
            ):
                self._last_accept_ms[side] = now_ms
                if side == "left":
                    p1_pressed = True
                else:
                    p2_pressed = True
            self._previous_held[side] = current

        return ButtonPresses(p1=p1_pressed, p2=p2_pressed)


class SimButtonReader:
    """In-memory button reader for tests."""

    def __init__(
        self,
        states: dict[ButtonSide, bool] | None = None,
    ) -> None:
        """Track held button states."""
        self.states: dict[ButtonSide, bool] = states or {
            "left": False,
            "right": False,
        }

    def read_states(self) -> dict[ButtonSide, bool]:
        """Return the configured held states."""
        return dict(self.states)
