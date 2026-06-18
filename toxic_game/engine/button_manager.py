"""Button input manager for edge-triggered player presses."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from toxic_game.config import GpioConfig, InputType, build_gpio_config
from toxic_game.engine.presence import HeldStates
from toxic_game.hw.gpio_input import ButtonSide, debounce_accept, read_button_states

_BUTTON_SIDES: tuple[ButtonSide, ...] = ("left", "right")
_SIDE_INPUT_ATTR: dict[ButtonSide, str] = {"left": "p1_input", "right": "p2_input"}


@dataclass(frozen=True, slots=True)
class ButtonPresses:
    """Edge-triggered presses detected since the previous poll."""

    p1: bool
    p2: bool


@dataclass(slots=True)
class _JumppadSideState:
    airborne: bool
    airborne_since_ms: int
    last_trigger_ms: int
    synced: bool


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
    """Detect player input edges for buttons and jumppad landings."""

    def __init__(
        self,
        reader: ButtonReader | None = None,
        *,
        gpio_config: GpioConfig | None = None,
        debounce_ms: int | None = None,
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        """Configure the manager with a reader and GPIO settings."""
        self._reader = reader or CallableButtonReader(read_button_states)
        self._gpio_config = gpio_config or build_gpio_config()
        self._debounce_ms = (
            self._gpio_config.debounce_ms if debounce_ms is None else debounce_ms
        )
        self._clock_ms = clock_ms or (lambda: int(time.monotonic() * 1000))
        self._previous_held = dict.fromkeys(_BUTTON_SIDES, False)
        self._last_accept_ms = dict.fromkeys(_BUTTON_SIDES, 0)
        self._jumppad_state = {
            side: _JumppadSideState(
                airborne=False,
                airborne_since_ms=0,
                last_trigger_ms=0,
                synced=False,
            )
            for side in _BUTTON_SIDES
        }

    def _input_type(self, side: ButtonSide) -> InputType:
        attr = _SIDE_INPUT_ATTR[side]
        return getattr(self._gpio_config, attr)

    def _poll_button_side(
        self,
        side: ButtonSide,
        *,
        connected: bool,
        previous_connected: bool,
        now_ms: int,
    ) -> bool:
        rising_edge = connected and not previous_connected
        if rising_edge and debounce_accept(
            self._last_accept_ms[side],
            now_ms,
            self._debounce_ms,
        ):
            self._last_accept_ms[side] = now_ms
            return True
        return False

    def _poll_jumppad_side(
        self,
        side: ButtonSide,
        *,
        connected: bool,
        previous_connected: bool,
        now_ms: int,
    ) -> bool:
        state = self._jumppad_state[side]
        if not state.synced:
            state.airborne = not connected
            if not connected:
                state.airborne_since_ms = now_ms
            state.synced = True
            return False

        if not connected and previous_connected:
            state.airborne = True
            state.airborne_since_ms = now_ms
            return False

        if connected and not previous_connected:
            if not state.airborne:
                return False
            air_ms = now_ms - state.airborne_since_ms
            since_trigger = now_ms - state.last_trigger_ms
            state.airborne = False
            if (
                air_ms >= self._gpio_config.jumppad.min_air_ms
                and since_trigger >= self._gpio_config.jumppad.retrigger_ms
            ):
                state.last_trigger_ms = now_ms
                return True
            return False

        if not connected:
            state.airborne = True
        else:
            state.airborne = False
        return False

    def poll(self) -> ButtonPresses:
        """Return buttons pressed since the last poll."""
        now_ms = self._clock_ms()
        states = self._reader.read_states()
        p1_pressed = False
        p2_pressed = False

        for side in _BUTTON_SIDES:
            connected = bool(states.get(side, False))
            previous_connected = self._previous_held[side]
            if self._input_type(side) == "jumppad":
                pressed = self._poll_jumppad_side(
                    side,
                    connected=connected,
                    previous_connected=previous_connected,
                    now_ms=now_ms,
                )
            else:
                pressed = self._poll_button_side(
                    side,
                    connected=connected,
                    previous_connected=previous_connected,
                    now_ms=now_ms,
                )
            if pressed:
                if side == "left":
                    p1_pressed = True
                else:
                    p2_pressed = True
            self._previous_held[side] = connected

        return ButtonPresses(p1=p1_pressed, p2=p2_pressed)

    def held_states(self) -> HeldStates:
        """Return whether each player's contact circuit is currently closed."""
        states = self._reader.read_states()
        return HeldStates(
            p1=bool(states.get("left", False)),
            p2=bool(states.get("right", False)),
        )


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
