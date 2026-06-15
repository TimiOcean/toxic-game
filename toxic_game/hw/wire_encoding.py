"""Encode mixed RGB + RGBW strips for rpi_ws281x."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from toxic_game.engine.led_frames import RgbPixel


def encode_pixel_bytes(*, channels: dict[str, int], order: str) -> bytes:
    """Pack color channels into wire bytes using a channel order string."""
    return bytes(channels[channel] for channel in order)


def build_mixed_wire_buffer(
    *,
    muted_rgb_count: int,
    active_pixels: tuple[RgbPixel, ...],
    muted_rgb_byte_order: str,
    rgbw_byte_order: str,
) -> bytes:
    """Build the on-wire byte stream for muted RGB + active RGBW segments."""
    wire = bytearray()
    off = {channel: 0 for channel in muted_rgb_byte_order}
    for _ in range(muted_rgb_count):
        wire.extend(encode_pixel_bytes(channels=off, order=muted_rgb_byte_order))

    for red, green, blue in active_pixels:
        wire.extend(
            encode_pixel_bytes(
                channels={"R": red, "G": green, "B": blue, "W": 0},
                order=rgbw_byte_order,
            ),
        )
    return bytes(wire)


def logical_pixel_count(*, muted_rgb_count: int, rgbw_count: int) -> int:
    """Return logical 3-byte pixels needed to emit the mixed wire stream."""
    wire_length = muted_rgb_count * 3 + rgbw_count * 4
    return (wire_length + 2) // 3


def wire_bytes_to_rgb_colors(wire: bytes) -> list[tuple[int, int, int]]:
    """Split a wire byte stream into RGB values for WS2811_STRIP_GRB pixels."""
    padded = wire + bytes((3 - len(wire) % 3) % 3)
    colors: list[tuple[int, int, int]] = []
    for index in range(0, len(padded), 3):
        green, red, blue = padded[index], padded[index + 1], padded[index + 2]
        colors.append((red, green, blue))
    return colors
