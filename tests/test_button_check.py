"""Tests for the button check CLI."""

from __future__ import annotations

from toxic_game.config import GpioConfig, JumppadConfig
from toxic_game.engine.button_manager import ButtonManager, ButtonPresses, SimButtonReader
from toxic_game.tools.button_check import ButtonCheckOptions, run_button_check


def _button_gpio_config() -> GpioConfig:
    return GpioConfig(
        left_contact_pin=17,
        right_contact_pin=27,
        debounce_ms=30,
        p1_input="button",
        p2_input="button",
        jumppad=JumppadConfig(min_air_ms=200, retrigger_ms=400),
    )


def test_run_button_check_runs_multiple_samples() -> None:
    reader = SimButtonReader({"left": False, "right": False})
    manager = ButtonManager(
        reader=reader,
        gpio_config=_button_gpio_config(),
        debounce_ms=0,
        clock_ms=lambda: 1000,
    )
    poll_count = {"n": 0}

    def count_poll() -> ButtonPresses:
        poll_count["n"] += 1
        return manager.poll()

    class _CountingPoller:
        def poll(self) -> ButtonPresses:
            return count_poll()

    run_button_check(
        options=ButtonCheckOptions(samples=3, interval_s=0.0, show_held=False),
        manager=_CountingPoller(),
        reader=reader,
        sleep=lambda _seconds: None,
        stdout=lambda _message: None,
    )

    assert poll_count["n"] == 3


def test_run_button_check_prints_press_events() -> None:
    reader = SimButtonReader({"left": False, "right": False})
    manager = ButtonManager(
        reader=reader,
        gpio_config=_button_gpio_config(),
        debounce_ms=0,
        clock_ms=lambda: 1000,
    )
    messages: list[str] = []

    def advance() -> None:
        reader.states["left"] = True

    advance()
    run_button_check(
        options=ButtonCheckOptions(samples=1, interval_s=0.0, show_held=False),
        manager=manager,
        reader=reader,
        sleep=lambda _seconds: None,
        stdout=messages.append,
    )

    assert any("P1 pressed" in message for message in messages)
