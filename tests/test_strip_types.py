"""Tests for RGBW strip type resolution."""

from __future__ import annotations

from toxic_game.hw import strip_types


def test_rgbw_strip_type_is_always_sk6812_rgbw(monkeypatch) -> None:
    calls: list[str] = []

    def fake_resolve(name: str) -> int:
        calls.append(name)
        return 0x18100800

    monkeypatch.setattr(strip_types, "resolve_strip_type", fake_resolve)

    assert strip_types.resolve_rgbw_strip_type("WRGB") == 0x18100800
    assert strip_types.resolve_rgbw_strip_type("GRBW") == 0x18100800
    assert calls == ["SK6812_STRIP_RGBW", "SK6812_STRIP_RGBW"]
