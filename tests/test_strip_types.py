"""Tests for RGBW strip type resolution."""

from __future__ import annotations

from toxic_game.hw.strip_types import resolve_rgbw_strip_type


def test_rgbw_strip_type_is_always_sk6812_rgbw() -> None:
    from rpi_ws281x import ws

    assert resolve_rgbw_strip_type("WRGB") == ws.SK6812_STRIP_RGBW
    assert resolve_rgbw_strip_type("GRBW") == ws.SK6812_STRIP_RGBW
