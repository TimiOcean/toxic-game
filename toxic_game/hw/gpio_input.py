"""GPIO helpers for reading physical button inputs."""

from __future__ import annotations

import importlib
from typing import Literal, Protocol, cast

from toxic_game.config import build_gpio_config

ButtonSide = Literal["left", "right"]


class GPIOProtocol(Protocol):
    """Subset of the RPi.GPIO module used by the input adapter."""

    BCM: int
    IN: int
    LOW: int
    PUD_UP: int

    def setmode(self, mode: int) -> None:
        """Set the numbering mode."""

    def setup(self, channel: int, direction: int, *, pull_up_down: int) -> None:
        """Configure one GPIO channel."""

    def input(self, channel: int) -> int:
        """Read one GPIO channel."""


def debounce_accept(last_ms: int, now_ms: int, threshold_ms: int) -> bool:
    """Return True when the elapsed time exceeds the configured threshold."""
    if threshold_ms < 0:
        message = "threshold_ms must be >= 0"
        raise ValueError(message)
    if now_ms < last_ms:
        return False
    return (now_ms - last_ms) >= threshold_ms


def _load_gpio_module() -> GPIOProtocol | None:
    """Lazily import the GPIO driver when it is available."""
    import sys

    search_paths = ("", "/usr/lib/python3/dist-packages")
    for path in search_paths:
        if path and path not in sys.path:
            sys.path.append(path)
        try:
            return cast("GPIOProtocol", importlib.import_module("RPi.GPIO"))
        except ImportError:
            continue
    return None


def gpio_is_available() -> bool:
    """Return True when the GPIO driver can be imported."""
    return _load_gpio_module() is not None


def _side_pin(side: ButtonSide) -> int:
    """Return the configured GPIO pin for the given button side."""
    config = build_gpio_config()
    if side == "left":
        return config.left_contact_pin
    return config.right_contact_pin


def read_button_states() -> dict[ButtonSide, bool]:
    """Return the pressed state for each player button (active-low)."""
    gpio = _load_gpio_module()
    if gpio is None:
        return {"left": False, "right": False}

    states: dict[ButtonSide, bool] = {"left": False, "right": False}
    try:
        gpio.setmode(gpio.BCM)
        for side in ("left", "right"):
            pin = _side_pin(side)
            gpio.setup(pin, gpio.IN, pull_up_down=gpio.PUD_UP)
            states[side] = gpio.input(pin) == gpio.LOW
    except (RuntimeError, AttributeError):
        return {"left": False, "right": False}
    return states
