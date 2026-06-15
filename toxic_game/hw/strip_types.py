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
