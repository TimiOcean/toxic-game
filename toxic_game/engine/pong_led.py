"""LED projection for the Pong game mode.

Reuses the rhythm game's marker geometry and LED primitives without modifying
any rhythm gameplay behavior.
"""

from __future__ import annotations

from typing import Literal

from toxic_game.config import LedConfig
from toxic_game.engine.led_frames import (
    GOLD,
    OFF,
    PLAYER_COLORS,
    RED,
    RgbPixel,
    WHITE,
    LedFrame,
    blank_pixels,
    build_frame,
    scale_pixel,
)
from toxic_game.engine.led_gameplay import MARKER_INTENSITY, hit_marker_range
from toxic_game.engine.scoring import Judgement
from toxic_game.hw.led_patterns import chase_pixels

PlayerId = Literal[1, 2]

PARKED_BALL_INTENSITY = 0.25


def _merge_pixels(base: list[RgbPixel], overlay: tuple[RgbPixel, ...]) -> None:
    for index, color in enumerate(overlay):
        if color == OFF:
            continue
        existing = base[index]
        base[index] = (
            max(existing[0], color[0]),
            max(existing[1], color[1]),
            max(existing[2], color[2]),
        )


def ball_index_for_player(
    player: PlayerId,
    *,
    strip_len: int,
    span: int,
    fraction: float,
) -> int:
    """Return the ball head index that overlaps ``player``'s marker."""
    start, end = hit_marker_range(
        player=player,
        strip_len=strip_len,
        span=span,
        fraction=fraction,
    )
    return end if player == 1 else start


def _marker_pixels(
    *,
    strip_len: int,
    span: int,
    led: LedConfig,
    hidden_players: frozenset[PlayerId],
) -> list[RgbPixel]:
    pixels = blank_pixels(strip_len)
    for player in (1, 2):
        if player in hidden_players:
            continue
        start, end = hit_marker_range(
            player=player,  # type: ignore[arg-type]
            strip_len=strip_len,
            span=span,
            fraction=led.hit_marker_fraction,
        )
        lit = scale_pixel(PLAYER_COLORS[player], MARKER_INTENSITY)  # type: ignore[index]
        for index in range(start, end + 1):
            pixels[index] = lit
    return pixels


def _feedback_color(judgement: Judgement) -> RgbPixel:
    if judgement == Judgement.PERFECT:
        return WHITE
    if judgement == Judgement.GOOD:
        return GOLD
    return RED


def _feedback_pixels(
    *,
    strip_len: int,
    player: PlayerId,
    judgement: Judgement,
    age_ms: int,
    led: LedConfig,
) -> tuple[RgbPixel, ...]:
    if age_ms < 0 or age_ms >= led.hit_flash_ms:
        return tuple(OFF for _ in range(strip_len))

    size = max(2, round(strip_len * 0.15))
    size = min(size, strip_len)
    remaining = 1.0 - age_ms / max(led.hit_flash_ms, 1)
    base = _feedback_color(judgement)

    pixels = blank_pixels(strip_len)
    if player == 1:
        lit_start, lit_end = 0, size - 1
    else:
        lit_start, lit_end = strip_len - size, strip_len - 1

    for index in range(lit_start, lit_end + 1):
        d = index - lit_start if player == 1 else lit_end - index
        falloff = 1.0 - (d / max(size - 1, 1)) * 0.5
        pixels[index] = scale_pixel(base, max(0.0, falloff) * remaining)

    end_index = 0 if player == 1 else strip_len - 1
    pixels[end_index] = base
    return tuple(pixels)


def build_flash_frame(strip_len: int, color: RgbPixel) -> LedFrame:
    """Return a frame with every gameplay LED set to ``color``."""
    return build_frame([color for _ in range(strip_len)])


def build_pong_frame(
    *,
    strip_len: int,
    led: LedConfig,
    ball_head_index: int,
    ball_color: RgbPixel,
    ball_visible: bool,
    ball_parked: bool,
    travel_right_to_left: bool,
    feedback: tuple[tuple[PlayerId, Judgement, int], ...] = (),
) -> LedFrame:
    """Render markers, the ball, and any active hit/miss flashes.

    ``feedback`` entries are ``(player, judgement, age_ms)`` tuples.
    """
    hidden_players: set[PlayerId] = set()
    for player, _judgement, age_ms in feedback:
        if 0 <= age_ms < led.hit_flash_ms:
            hidden_players.add(player)

    pixels = _marker_pixels(
        strip_len=strip_len,
        span=led.marker_span,
        led=led,
        hidden_players=frozenset(hidden_players),
    )

    if ball_visible:
        color = scale_pixel(ball_color, PARKED_BALL_INTENSITY) if ball_parked else ball_color
        _merge_pixels(
            pixels,
            chase_pixels(
                strip_len,
                ball_head_index,
                led.running_light_span,
                color,
                travel_right_to_left=travel_right_to_left,
                brightness_ramp=False,
                tail_length=led.running_light_tail,
            ),
        )

    for player, judgement, age_ms in feedback:
        _merge_pixels(
            pixels,
            _feedback_pixels(
                strip_len=strip_len,
                player=player,
                judgement=judgement,
                age_ms=age_ms,
                led=led,
            ),
        )

    return build_frame(pixels)
