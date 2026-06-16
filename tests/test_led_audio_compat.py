"""Tests for LED/audio coexistence helpers."""

from __future__ import annotations

from toxic_game.hw.led_audio_compat import led_audio_conflict_message


def test_spi_pin_has_no_conflict_message(monkeypatch) -> None:
    monkeypatch.setattr(
        "toxic_game.hw.led_audio_compat.analog_audio_module_loaded",
        lambda: True,
    )

    assert led_audio_conflict_message(pin=10) is None


def test_pwm_pin_warns_when_analog_audio_loaded(monkeypatch) -> None:
    monkeypatch.setattr(
        "toxic_game.hw.led_audio_compat.analog_audio_module_loaded",
        lambda: True,
    )

    message = led_audio_conflict_message(pin=18)

    assert message is not None
    assert "GPIO 10" in message


def test_pwm_pin_ok_when_audio_unloaded(monkeypatch) -> None:
    monkeypatch.setattr(
        "toxic_game.hw.led_audio_compat.analog_audio_module_loaded",
        lambda: False,
    )

    assert led_audio_conflict_message(pin=18) is None
