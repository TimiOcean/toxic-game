"""Tests for mixed RGB + RGBW wire encoding."""

from __future__ import annotations

from toxic_game.hw.wire_encoding import (
    build_mixed_wire_buffer,
    logical_pixel_count,
    wire_bytes_to_rgb_colors,
)


def test_magenta_rgbw_bytes_use_configured_order() -> None:
    wire_grbw = build_mixed_wire_buffer(
        muted_rgb_count=0,
        active_pixels=((255, 0, 255),),
        muted_rgb_byte_order="GRB",
        rgbw_byte_order="GRBW",
    )
    wire_rgbw = build_mixed_wire_buffer(
        muted_rgb_count=0,
        active_pixels=((255, 0, 255),),
        muted_rgb_byte_order="GRB",
        rgbw_byte_order="RGBW",
    )
    wire_wrgb = build_mixed_wire_buffer(
        muted_rgb_count=0,
        active_pixels=((255, 0, 255),),
        muted_rgb_byte_order="GRB",
        rgbw_byte_order="WRGB",
    )

    assert wire_grbw == bytes([0, 255, 255, 0])
    assert wire_rgbw == bytes([255, 0, 255, 0])
    assert wire_wrgb == bytes([0, 255, 0, 255])


def test_mixed_wire_length_for_60_rgb_and_60_rgbw() -> None:
    wire = build_mixed_wire_buffer(
        muted_rgb_count=60,
        active_pixels=((255, 0, 255),),
        muted_rgb_byte_order="GRB",
        rgbw_byte_order="WRGB",
    )

    assert len(wire) == 60 * 3 + 4
    assert wire[: 60 * 3] == bytes(60 * 3)
    assert wire[60 * 3 :] == bytes([0, 255, 0, 255])


def test_logical_pixel_count_for_mixed_strip() -> None:
    assert logical_pixel_count(muted_rgb_count=60, rgbw_count=60) == 140


def test_wire_bytes_split_into_grb_logical_pixels() -> None:
    wire = bytes([0, 10, 20, 30, 40, 50])
    colors = wire_bytes_to_rgb_colors(wire)

    assert colors == [(10, 0, 20), (40, 30, 50)]
