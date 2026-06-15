"""Map logical RGB colors to rpi_ws281x RGBW Color() arguments."""

from __future__ import annotations

_VALID_CHANNELS = frozenset("WRGB")


def rgbw_color_args(
    red: int,
    green: int,
    blue: int,
    *,
    byte_order: str,
    white: int = 0,
) -> tuple[int, int, int, int]:
    """Map logical RGB to Color(R, G, B, W) for the configured wire byte order.

    rpi_ws281x always transmits SK6812 pixels as R, G, B, W bytes on the data
    line. ``byte_order`` describes how those four wire bytes map to physical
    channels (e.g. ``WRGB`` means byte 0 is W, byte 1 is R, ...).
    """
    order = byte_order.upper()
    if len(order) != 4 or set(order) != _VALID_CHANNELS:
        message = f"rgbw_byte_order must be a permutation of WRGB, got {byte_order!r}"
        raise ValueError(message)

    channels = {"W": white, "R": red, "G": green, "B": blue}
    return (
        channels[order[0]],
        channels[order[1]],
        channels[order[2]],
        channels[order[3]],
    )
