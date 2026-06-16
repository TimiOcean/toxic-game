"""Shared cooperative health pool rules."""

from __future__ import annotations

from dataclasses import dataclass

from toxic_game.config import HealthConfig
from toxic_game.engine.scoring import Judgement


@dataclass(frozen=True, slots=True)
class HealthState:
    """Current health and game-over status."""

    value: int
    max_value: int

    @property
    def is_game_over(self) -> bool:
        """Return True when health reached zero."""
        return self.value <= 0


def make_health_state(config: HealthConfig) -> HealthState:
    """Create initial health state from config."""
    start = min(max(config.start, 0), config.max)
    return HealthState(value=start, max_value=config.max)


def apply_judgement(
    *,
    state: HealthState,
    judgement: Judgement | None,
    config: HealthConfig,
) -> HealthState:
    """Apply a judgement result to the cooperative health pool."""
    next_value = state.value
    if judgement == Judgement.PERFECT:
        next_value += config.gain_on_perfect
    elif judgement == Judgement.GOOD:
        next_value += config.gain_on_good
    elif judgement == Judgement.ERROR:
        next_value -= config.lose_on_error

    next_value = min(max(next_value, 0), state.max_value)
    return HealthState(value=next_value, max_value=state.max_value)
