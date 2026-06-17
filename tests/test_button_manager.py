"""Tests for button edge detection."""

from __future__ import annotations

from toxic_game.config import GpioConfig, JumppadConfig
from toxic_game.engine.button_manager import ButtonManager, SimButtonReader


def _gpio_config(**overrides: object) -> GpioConfig:
    defaults = {
        "left_contact_pin": 17,
        "right_contact_pin": 27,
        "debounce_ms": 30,
        "p1_input": "button",
        "p2_input": "button",
        "jumppad": JumppadConfig(min_air_ms=200, retrigger_ms=400),
    }
    defaults.update(overrides)
    return GpioConfig(**defaults)  # type: ignore[arg-type]


def test_poll_reports_rising_edge_once_while_held() -> None:
    reader = SimButtonReader({"left": True, "right": False})
    manager = ButtonManager(
        reader=reader,
        gpio_config=_gpio_config(),
        debounce_ms=0,
        clock_ms=lambda: 1000,
    )

    first = manager.poll()
    second = manager.poll()

    assert first.p1 is True
    assert first.p2 is False
    assert second.p1 is False
    assert second.p2 is False


def test_poll_detects_p2_press() -> None:
    reader = SimButtonReader({"left": False, "right": True})
    manager = ButtonManager(
        reader=reader,
        gpio_config=_gpio_config(),
        debounce_ms=0,
        clock_ms=lambda: 1000,
    )

    presses = manager.poll()

    assert presses.p1 is False
    assert presses.p2 is True


def test_poll_ignores_release_without_press() -> None:
    reader = SimButtonReader({"left": True, "right": False})
    manager = ButtonManager(
        reader=reader,
        gpio_config=_gpio_config(),
        debounce_ms=0,
        clock_ms=lambda: 1000,
    )
    manager.poll()

    reader.states["left"] = False
    presses = manager.poll()

    assert presses.p1 is False
    assert presses.p2 is False


def test_debounce_blocks_rapid_retrigger() -> None:
    clock = {"now": 1000}
    reader = SimButtonReader({"left": False, "right": False})
    manager = ButtonManager(
        reader=reader,
        gpio_config=_gpio_config(),
        debounce_ms=30,
        clock_ms=lambda: clock["now"],
    )

    reader.states["left"] = True
    assert manager.poll().p1 is True

    reader.states["left"] = False
    manager.poll()

    reader.states["left"] = True
    clock["now"] = 1010
    assert manager.poll().p1 is False

    reader.states["left"] = False
    manager.poll()

    reader.states["left"] = True
    clock["now"] = 1030
    assert manager.poll().p1 is True


def test_new_press_after_release_is_detected() -> None:
    clock = {"now": 1000}
    reader = SimButtonReader({"left": False, "right": False})
    manager = ButtonManager(
        reader=reader,
        gpio_config=_gpio_config(),
        debounce_ms=0,
        clock_ms=lambda: clock["now"],
    )

    reader.states["left"] = True
    manager.poll()
    reader.states["left"] = False
    manager.poll()

    clock["now"] = 1100
    reader.states["left"] = True
    presses = manager.poll()

    assert presses.p1 is True


def test_jumppad_triggers_on_landing_after_minimum_air_time() -> None:
    clock = {"now": 1000}
    reader = SimButtonReader({"left": True, "right": False})
    manager = ButtonManager(
        reader=reader,
        gpio_config=_gpio_config(p1_input="jumppad"),
        clock_ms=lambda: clock["now"],
    )

    assert manager.poll().p1 is False

    reader.states["left"] = False
    manager.poll()
    clock["now"] = 1150
    reader.states["left"] = True
    assert manager.poll().p1 is False

    reader.states["left"] = False
    manager.poll()
    clock["now"] = 1400
    reader.states["left"] = True
    assert manager.poll().p1 is True


def test_jumppad_ignores_brief_disconnect() -> None:
    clock = {"now": 1000}
    reader = SimButtonReader({"left": True, "right": False})
    manager = ButtonManager(
        reader=reader,
        gpio_config=_gpio_config(p1_input="jumppad"),
        clock_ms=lambda: clock["now"],
    )
    manager.poll()

    reader.states["left"] = False
    manager.poll()
    clock["now"] = 1100
    reader.states["left"] = True
    assert manager.poll().p1 is False


def test_jumppad_retrigger_cooldown() -> None:
    clock = {"now": 1000}
    reader = SimButtonReader({"left": True, "right": False})
    manager = ButtonManager(
        reader=reader,
        gpio_config=_gpio_config(p1_input="jumppad"),
        clock_ms=lambda: clock["now"],
    )
    manager.poll()

    reader.states["left"] = False
    manager.poll()
    clock["now"] = 1300
    reader.states["left"] = True
    assert manager.poll().p1 is True

    reader.states["left"] = False
    manager.poll()
    clock["now"] = 1450
    reader.states["left"] = True
    assert manager.poll().p1 is False

    reader.states["left"] = False
    manager.poll()
    clock["now"] = 1700
    reader.states["left"] = True
    assert manager.poll().p1 is True


def test_jumppad_does_not_trigger_on_initial_connection() -> None:
    reader = SimButtonReader({"left": True, "right": False})
    manager = ButtonManager(
        reader=reader,
        gpio_config=_gpio_config(p1_input="jumppad"),
        clock_ms=lambda: 1000,
    )

    assert manager.poll().p1 is False
