"""Tests for game check CLI helpers."""

from __future__ import annotations

from pathlib import Path

from toxic_game.tools.game_check import ensure_dummy_taps


def test_ensure_dummy_taps_writes_both_players(tmp_path: Path) -> None:
    ensure_dummy_taps(tmp_path, bars=4)

    p1 = (tmp_path / "p1.taps").read_text(encoding="utf-8").strip().splitlines()
    p2 = (tmp_path / "p2.taps").read_text(encoding="utf-8").strip().splitlines()

    assert len(p1) == 4
    assert len(p2) == 4
    assert p1[0] == "1.2"
    assert p2[0] == "1.4"
