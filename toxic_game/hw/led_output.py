"""LED output abstractions for Toxic Game."""

from __future__ import annotations

import importlib
from typing import Protocol, cast

from toxic_game.config import build_led_config
from toxic_game.engine.led_frames import LedFrame, RgbPixel
from toxic_game.hw.rgbw_color import rgbw_color_args
from toxic_game.hw.strip_types import resolve_rgbw_strip_type


def build_driver_pixels(
    frame: LedFrame,
    *,
    muted_rgbw_count: int,
    rgbw_count: int,
) -> tuple[RgbPixel, ...]:
    """Build the uniform RGBW buffer sent to rpi_ws281x.

    Leading black pixels clock through the physical RGB-only segment; gameplay
    pixels follow on the RGBW segment.
    """
    muted = ((0, 0, 0),) * muted_rgbw_count
    return muted + frame.pixels[:rgbw_count]


class PixelStripProtocol(Protocol):
    """Subset of the rpi_ws281x PixelStrip API used by the adapter."""

    def begin(self) -> None:
        """Initialize the strip."""

    def setPixelColor(self, index: int, color: int) -> None:  # noqa: N802
        """Set one pixel's color."""

    def show(self) -> None:
        """Flush the current pixel buffer."""


class LedOutput(Protocol):
    """Protocol for objects that render LED frames."""

    def write_frame(self, frame: LedFrame) -> None:
        """Render the provided LED frame."""


class NoOpLedOutput:
    """LED output that discards every frame."""

    def write_frame(self, frame: LedFrame) -> None:
        """Drop the frame without acting on it."""
        _ = frame


class SimLedOutput:
    """In-memory LED output useful for tests."""

    def __init__(self) -> None:
        """Track frames as RGB tuples."""
        self.frames: list[tuple[tuple[int, int, int], ...]] = []

    def write_frame(self, frame: LedFrame) -> None:
        """Store the current frame for later assertions."""
        self.frames.append(frame.pixels)


class Ws2811LedOutput:
    """Best-effort physical LED strip output backed by rpi_ws281x."""

    def __init__(self) -> None:
        """Initialize the physical strip when the dependency is available."""
        self._strip = self._build_strip()
        self._color_factory = self._load_color_factory()

    def _load_color_factory(self):
        try:
            module = importlib.import_module("rpi_ws281x")
        except ImportError:
            return None
        return getattr(module, "Color", None)

    def _build_strip(self) -> PixelStripProtocol | None:
        try:
            module = importlib.import_module("rpi_ws281x")
        except ImportError:
            return None

        strip_class = getattr(module, "PixelStrip", None)
        color_factory = getattr(module, "Color", None)
        if strip_class is None or color_factory is None:
            return None

        config = build_led_config()

        strip = strip_class(
            config.driver_count,
            config.pin,
            config.freq_hz,
            config.dma,
            config.invert,
            config.brightness,
            config.channel,
            strip_type=resolve_rgbw_strip_type(config.rgbw_byte_order),
        )
        strip.begin()
        return cast("PixelStripProtocol", strip)

    def write_frame(self, frame: LedFrame) -> None:
        """Push the current frame to the physical strip."""
        if self._strip is None or self._color_factory is None:
            return

        config = build_led_config()
        pixels = build_driver_pixels(
            frame,
            muted_rgbw_count=config.muted_rgbw_count,
            rgbw_count=config.rgbw_count,
        )

        for index, (red, green, blue) in enumerate(pixels):
            color_args = rgbw_color_args(
                red,
                green,
                blue,
                byte_order=config.rgbw_byte_order,
            )
            self._strip.setPixelColor(
                index,
                self._color_factory(*color_args),
            )

        self._strip.show()
