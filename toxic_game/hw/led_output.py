"""LED output abstractions for Toxic Game."""

from __future__ import annotations

import importlib
from typing import Protocol, cast

from toxic_game.config import LedConfig, build_led_config
from toxic_game.engine.led_frames import LedFrame, RgbPixel
from toxic_game.hw.strip_types import resolve_strip_type
from toxic_game.hw.wire_encoding import (
    build_mixed_wire_buffer,
    logical_pixel_count,
    wire_bytes_to_rgb_colors,
)


def map_logical_frame_to_physical(
    frame: LedFrame,
    *,
    muted_rgb_count: int,
    rgbw_count: int,
) -> tuple[RgbPixel, ...]:
    """Map a logical RGBW frame onto the active strip segment."""
    _ = muted_rgb_count
    return frame.pixels[:rgbw_count]


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
        strip_count, strip_type = self._strip_layout(config)

        strip = strip_class(
            strip_count,
            config.pin,
            config.freq_hz,
            config.dma,
            config.invert,
            config.brightness,
            config.channel,
            strip_type=strip_type,
        )
        strip.begin()
        return cast("PixelStripProtocol", strip)

    @staticmethod
    def _strip_layout(config: LedConfig) -> tuple[int, int]:
        if config.muted_rgb_count == 0:
            return config.rgbw_count, resolve_strip_type(config.rgbw_strip_type)
        return (
            logical_pixel_count(
                muted_rgb_count=config.muted_rgb_count,
                rgbw_count=config.rgbw_count,
            ),
            resolve_strip_type(config.muted_rgb_strip_type),
        )

    def write_frame(self, frame: LedFrame) -> None:
        """Push the current frame to the physical strip."""
        if self._strip is None or self._color_factory is None:
            return

        config = build_led_config()
        active_pixels = map_logical_frame_to_physical(
            frame,
            muted_rgb_count=config.muted_rgb_count,
            rgbw_count=config.rgbw_count,
        )

        if config.muted_rgb_count == 0:
            for index, (red, green, blue) in enumerate(active_pixels):
                self._strip.setPixelColor(
                    index,
                    self._color_factory(red, green, blue, 0),
                )
        else:
            wire = build_mixed_wire_buffer(
                muted_rgb_count=config.muted_rgb_count,
                active_pixels=active_pixels,
                muted_rgb_byte_order=config.muted_rgb_byte_order,
                rgbw_byte_order=config.rgbw_byte_order,
            )
            for index, (red, green, blue) in enumerate(wire_bytes_to_rgb_colors(wire)):
                self._strip.setPixelColor(
                    index,
                    self._color_factory(red, green, blue),
                )

        self._strip.show()
