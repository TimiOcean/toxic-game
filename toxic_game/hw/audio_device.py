"""ALSA device helpers for routing pygame to the 3.5 mm jack."""

from __future__ import annotations

import os
import re
from pathlib import Path

_HEADPHONE_LINE_PATTERN = re.compile(r"^\s*(\d+)\s+\[([^\]]+)\]")


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
