"""Tests for GPIO availability fallback."""

from __future__ import annotations

from toxic_game.hw import gpio_input


def test_gpio_is_available_when_driver_imports(monkeypatch) -> None:
    monkeypatch.setattr(gpio_input, "_load_gpio_module", lambda: object())
    assert gpio_input.gpio_is_available() is True


def test_gpio_is_unavailable_when_driver_missing(monkeypatch) -> None:
    monkeypatch.setattr(gpio_input, "_load_gpio_module", lambda: None)
    assert gpio_input.gpio_is_available() is False
