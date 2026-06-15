"""Tests for GPIO debounce helper."""

from __future__ import annotations

import pytest

from toxic_game.hw.gpio_input import debounce_accept

BASE_TIMESTAMP_MS = 1000
DEFAULT_THRESHOLD_MS = 30


def test_debounce_rejects_within_threshold() -> None:
    assert (
        debounce_accept(
            last_ms=BASE_TIMESTAMP_MS,
            now_ms=BASE_TIMESTAMP_MS + 10,
            threshold_ms=DEFAULT_THRESHOLD_MS,
        )
        is False
    )


def test_debounce_accepts_after_threshold() -> None:
    assert (
        debounce_accept(
            last_ms=BASE_TIMESTAMP_MS,
            now_ms=BASE_TIMESTAMP_MS + 40,
            threshold_ms=DEFAULT_THRESHOLD_MS,
        )
        is True
    )


def test_debounce_accepts_at_threshold_boundary() -> None:
    assert (
        debounce_accept(
            last_ms=BASE_TIMESTAMP_MS,
            now_ms=BASE_TIMESTAMP_MS + DEFAULT_THRESHOLD_MS,
            threshold_ms=DEFAULT_THRESHOLD_MS,
        )
        is True
    )


def test_debounce_rejects_negative_threshold() -> None:
    with pytest.raises(ValueError, match="threshold_ms must be >= 0"):
        debounce_accept(
            last_ms=BASE_TIMESTAMP_MS,
            now_ms=BASE_TIMESTAMP_MS + 10,
            threshold_ms=-1,
        )
