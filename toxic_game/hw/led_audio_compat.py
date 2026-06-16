"""Helpers for LED/audio coexistence on Raspberry Pi."""

from __future__ import annotations

from pathlib import Path

_PWM_AUDIO_CONFLICT_PINS = frozenset({12, 18, 13})


def analog_audio_module_loaded() -> bool:
    """Return True when the onboard analog audio driver is loaded."""
    modules = Path("/proc/modules").read_text(encoding="utf-8")
    return "snd_bcm2835" in modules


def pwm_audio_conflict(pin: int) -> bool:
    """Return True when PWM LED output likely conflicts with 3.5 mm audio."""
    return pin in _PWM_AUDIO_CONFLICT_PINS and analog_audio_module_loaded()


def led_audio_conflict_message(*, pin: int) -> str | None:
    """Return a user-facing warning when LED and headphone audio may conflict."""
    if pin == 10:
        return None
    if not pwm_audio_conflict(pin):
        return None
    return (
        "LED pin uses PWM hardware, which conflicts with 3.5 mm analog audio. "
        "Move strip data to GPIO 10 (SPI, physical pin 19), set led.pin = 10, "
        "enable dtparam=spi=on and core_freq=250 in /boot/firmware/config.txt, "
        "then reboot."
    )
