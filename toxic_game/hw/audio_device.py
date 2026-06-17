"""ALSA device helpers for routing pygame to the 3.5 mm jack."""

from __future__ import annotations

import importlib
import os
import re
from pathlib import Path

_HEADPHONE_LINE_PATTERN = re.compile(r"^\s*(\d+)\s+\[([^\]]+)\]")

# Default pygame buffer (512 samples) is too small on Raspberry Pi and often
# causes ALSA underruns / crackle on startup. 44.1 kHz stereo matches the
# headphone DAC and most decoded assets.
_MIXER_FREQUENCY_HZ = 44100
_MIXER_BUFFER_SAMPLES = 2048


def _device_from_cards_text(cards_text: str) -> str | None:
    for line in cards_text.splitlines():
        match = _HEADPHONE_LINE_PATTERN.match(line)
        if match is None:
            continue
        card_name = match.group(2)
        if "Headphones" in card_name or "bcm2835" in line:
            return f"plughw:{match.group(1)},0"
    return None


def find_headphone_alsa_device() -> str | None:
    """Return an ALSA device string for the onboard headphone jack, if present."""
    cards_path = Path("/proc/asound/cards")
    if not cards_path.exists():
        return None
    return _device_from_cards_text(cards_path.read_text(encoding="utf-8"))


def configure_headphone_audio() -> str | None:
    """Point SDL/pygame at the 3.5 mm jack when available."""
    os.environ.setdefault("SDL_AUDIODRIVER", "alsa")
    device = find_headphone_alsa_device()
    if device is not None:
        os.environ["AUDIODEV"] = device
    return device


def _warmup_mixer(mixer: object, sound_factory: object) -> None:
    """Prime the output device with a short silent sample."""
    try:
        # ~10 ms of silence at 44.1 kHz, stereo 16-bit.
        silent = sound_factory(buffer=b"\x00\x00" * 441)  # type: ignore[operator,call-arg]
        silent.play()  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        return


def ensure_pygame_mixer() -> object | None:
    """Initialize pygame.mixer once with Pi-friendly settings.

    Must be called (via :func:`configure_headphone_audio`) before pygame loads
    the audio backend. Returns the mixer module, or ``None`` when unavailable.
    """
    configure_headphone_audio()
    try:
        pygame = importlib.import_module("pygame")
    except ImportError:
        return None

    mixer = getattr(pygame, "mixer", None)
    if mixer is None:
        return None

    try:
        if not mixer.get_init():
            mixer.init(
                frequency=_MIXER_FREQUENCY_HZ,
                size=-16,
                channels=2,
                buffer=_MIXER_BUFFER_SAMPLES,
            )
            sound_factory = getattr(mixer, "Sound", None)
            if sound_factory is not None:
                _warmup_mixer(mixer, sound_factory)
        return mixer
    except Exception:  # noqa: BLE001
        try:
            if not mixer.get_init():
                mixer.init()
            return mixer
        except Exception:  # noqa: BLE001
            return None
