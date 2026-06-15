"""Map config strip type names to rpi_ws281x constants."""

from __future__ import annotations

import importlib


def resolve_strip_type(name: str) -> int:
    """Return the rpi_ws281x strip type constant for a config string."""
    module = importlib.import_module("rpi_ws281x").ws
    try:
        return int(getattr(module, name))
    except AttributeError as error:
        message = f"unsupported strip type: {name}"
        raise ValueError(message) from error


def resolve_rgbw_strip_type(byte_order: str) -> int:
    """Return the rpi_ws281x strip type used for uniform RGBW output.

    Wire byte order is handled separately via :func:`rgbw_color.rgbw_color_args`.
    """
    _ = byte_order
    return resolve_strip_type("SK6812_STRIP_RGBW")
