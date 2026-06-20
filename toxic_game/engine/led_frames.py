"""LED frame types and pixel helpers."""

from __future__ import annotations

from dataclasses import dataclass

RgbPixel = tuple[int, int, int]

OFF: RgbPixel = (0, 0, 0)
WHITE: RgbPixel = (255, 255, 255)
RED: RgbPixel = (255, 0, 0)
MAGENTA: RgbPixel = (255, 0, 255)
CYAN: RgbPixel = (0, 200, 255)
YELLOW: RgbPixel = (255, 255, 0)
GOLD: RgbPixel = (200, 140, 0)
GREY_WHITE: RgbPixel = (150, 150, 150)

# Canonical player colors — use everywhere (gameplay, score reveal, applause).
PLAYER_COLORS: dict[int, RgbPixel] = {1: MAGENTA, 2: CYAN}

NAMED_COLORS: dict[str, RgbPixel] = {
    "off": OFF,
    "red": RED,
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "white": WHITE,
    "magenta": MAGENTA,
    "cyan": CYAN,
    "yellow": YELLOW,
}


@dataclass(frozen=True, slots=True)
class LedFrame:
    """One complete LED strip frame."""

    pixels: tuple[RgbPixel, ...]


def blank_pixels(count: int) -> list[RgbPixel]:
    """Return a black pixel buffer of the requested length."""
    return [OFF for _ in range(count)]


def scale_pixel(color: RgbPixel, factor: float) -> RgbPixel:
    """Scale an RGB tuple by a 0-1 brightness factor."""
    clamped = min(max(factor, 0.0), 1.0)
    return (
        round(color[0] * clamped),
        round(color[1] * clamped),
        round(color[2] * clamped),
    )


def build_frame(pixels: list[RgbPixel] | tuple[RgbPixel, ...]) -> LedFrame:
    """Wrap pixels in a frame."""
    return LedFrame(pixels=tuple(pixels))
