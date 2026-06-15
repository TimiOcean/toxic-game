"""Tests for GPIO button input."""

from __future__ import annotations

import pytest

from toxic_game.config import GpioConfig, clear_config_cache
from toxic_game.hw import gpio_input


class _FakeGpioModule:
    BCM = 11
    IN = 1
    PUD_UP = 21
    LOW = 0
    HIGH = 1

    def __init__(self, values: dict[int, int]) -> None:
        self.values = values
        self.setup_calls: list[tuple[int, int, int]] = []
        self.mode_calls: list[int] = []

    def setmode(self, mode: int) -> None:
        self.mode_calls.append(mode)

    def setup(self, pin: int, direction: int, pull_up_down: int) -> None:
        self.setup_calls.append((pin, direction, pull_up_down))

    def input(self, pin: int) -> int:
        return self.values[pin]


@pytest.fixture(autouse=True)
def _clear_config_cache() -> None:
    clear_config_cache()


def test_read_button_states_returns_false_when_gpio_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gpio_input, "_load_gpio_module", lambda: None)

    assert gpio_input.read_button_states() == {"left": False, "right": False}


def test_read_button_states_uses_active_low_pull_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeGpioModule(values={17: _FakeGpioModule.LOW, 27: _FakeGpioModule.HIGH})
    monkeypatch.setattr(gpio_input, "_load_gpio_module", lambda: fake)
    monkeypatch.setattr(
        gpio_input,
        "build_gpio_config",
        lambda: GpioConfig(left_contact_pin=17, right_contact_pin=27, debounce_ms=30),
    )

    assert gpio_input.read_button_states() == {"left": True, "right": False}
    assert fake.mode_calls == [_FakeGpioModule.BCM]
    assert fake.setup_calls == [
        (17, _FakeGpioModule.IN, _FakeGpioModule.PUD_UP),
        (27, _FakeGpioModule.IN, _FakeGpioModule.PUD_UP),
    ]
