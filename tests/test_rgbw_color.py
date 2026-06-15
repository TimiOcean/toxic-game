"""Tests for logical RGB to rpi_ws281x Color() remapping."""

from __future__ import annotations

import pytest

from toxic_game.hw.rgbw_color import rgbw_color_args


def test_wrgb_red_maps_color_args_for_library_rgbw_wire() -> None:
    assert rgbw_color_args(255, 0, 0, byte_order="WRGB") == (0, 255, 0, 0)


def test_wrgb_green() -> None:
    assert rgbw_color_args(0, 255, 0, byte_order="WRGB") == (0, 0, 255, 0)


def test_wrgb_blue() -> None:
    assert rgbw_color_args(0, 0, 255, byte_order="WRGB") == (0, 0, 0, 255)


def test_wrgb_white() -> None:
    assert rgbw_color_args(255, 255, 255, byte_order="WRGB") == (0, 255, 255, 255)


def test_wrgb_magenta() -> None:
    assert rgbw_color_args(255, 0, 255, byte_order="WRGB") == (0, 255, 0, 255)


def test_invalid_byte_order_raises() -> None:
    with pytest.raises(ValueError, match="permutation of WRGB"):
        rgbw_color_args(255, 0, 0, byte_order="RGB")
