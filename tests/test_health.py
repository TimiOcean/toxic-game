"""Tests for cooperative health pool rules."""

from __future__ import annotations

from toxic_game.config import HealthConfig
from toxic_game.engine.health import apply_judgement, make_health_state
from toxic_game.engine.scoring import Judgement


def _health_config() -> HealthConfig:
    return HealthConfig(
        start=20,
        max=20,
        lose_on_error=2,
        gain_on_good=1,
        gain_on_perfect=2,
    )


def test_make_health_state_uses_start_value() -> None:
    state = make_health_state(_health_config())
    assert state.value == 20
    assert state.max_value == 20
    assert state.is_game_over is False


def test_perfect_increases_health_but_caps_at_max() -> None:
    config = _health_config()
    state = make_health_state(config)

    after = apply_judgement(state=state, judgement=Judgement.PERFECT, config=config)

    assert after.value == 20


def test_good_increases_by_one_when_below_max() -> None:
    config = _health_config()
    state = apply_judgement(
        state=make_health_state(config),
        judgement=Judgement.ERROR,
        config=config,
    )

    after = apply_judgement(state=state, judgement=Judgement.GOOD, config=config)

    assert state.value == 18
    assert after.value == 19


def test_error_reduces_health_and_hits_floor_at_zero() -> None:
    config = _health_config()
    state = make_health_state(config)
    for _ in range(15):
        state = apply_judgement(state=state, judgement=Judgement.ERROR, config=config)

    assert state.value == 0
    assert state.is_game_over is True


def test_ghost_tap_keeps_health_unchanged() -> None:
    config = _health_config()
    state = make_health_state(config)

    after = apply_judgement(state=state, judgement=None, config=config)

    assert after.value == state.value
