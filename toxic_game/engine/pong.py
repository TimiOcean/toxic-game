"""Pong game mode: a single bouncing running light between the two markers.

Reuses the rhythm game's input (:class:`ButtonManager`), marker geometry, and
LED output. Unlike the rhythm game, hits are judged by the LED *distance*
between the ball and the receiver's marker (not by time windows). The rhythm
gameplay modules are imported read-only and are not modified.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from toxic_game.config import JudgementWindowsMs, LedConfig, PongConfig, RuntimeConfig
from toxic_game.engine.button_manager import ButtonManager, ButtonPresses
from toxic_game.engine.led_frames import OFF, PLAYER_COLORS, RgbPixel, WHITE
from toxic_game.engine.presence import EmptyShutdownTracker, HeldStates
from toxic_game.engine.pong_led import (
    ball_index_for_player,
    build_pong_frame,
)
from toxic_game.engine.score_animation import (
    build_full_flash_frame,
    build_half_flash_frame,
    run_applause_animation,
    run_score_animation,
)
from toxic_game.engine.scoring import Judgement
from toxic_game.hw.led_output import LedOutput
from toxic_game.hw.sfx import NoOpSfxPlayer, SfxPlayer

PlayerId = Literal[1, 2]

PongState = Literal["rally", "point_flash", "game_over"]


class ButtonPoller(Protocol):
    """Protocol for button polling sources used by the Pong manager."""

    def poll(self) -> ButtonPresses:
        """Return edge-triggered button presses for this tick."""

    def held_states(self) -> HeldStates:
        """Return whether each player's contact circuit is currently closed."""


@dataclass(frozen=True, slots=True)
class _Feedback:
    player: PlayerId
    judgement: Judgement
    started_ms: int


@dataclass(frozen=True, slots=True)
class PongSnapshot:
    """One tick of Pong state."""

    now_ms: int
    state: PongState
    lives_p1: int
    lives_p2: int
    ball_index: int
    ball_color: RgbPixel
    from_player: PlayerId
    to_player: PlayerId
    perfect_count: int
    good_count: int
    miss_count: int
    rally_count: int
    game_over: bool
    abandoned: bool


def _other(player: PlayerId) -> PlayerId:
    return 2 if player == 1 else 1


class PongManager:
    """Drive the Pong rally, scoring, lives, SFX, and LED output."""

    def __init__(
        self,
        *,
        button_manager: ButtonPoller | None,
        led_output: LedOutput,
        led: LedConfig,
        windows: JudgementWindowsMs,
        pong: PongConfig,
        runtime: RuntimeConfig,
        sfx: SfxPlayer | None = None,
        auto_players: frozenset[PlayerId] = frozenset(),
        auto_miss_chance: float = 0.0,
        empty_shutdown_ms: int = 5000,
        clock_ms: Callable[[], int] | None = None,
        sleep: Callable[[float], None] | None = None,
        rng: Callable[[], float] | None = None,
    ) -> None:
        self._button_manager = button_manager or ButtonManager()
        self._led_output = led_output
        self._led = led
        self._windows = windows  # unused: Pong judges by LED distance
        self._pong = pong
        self._runtime = runtime
        self._sfx = sfx or NoOpSfxPlayer()
        self._auto_players = auto_players
        self._auto_miss_chance = auto_miss_chance
        self._clock_ms = clock_ms or (lambda: int(time.monotonic() * 1000))
        self._sleep = sleep or time.sleep
        self._rng = rng or random.random

        self._strip_len = led.active_count
        self._marker_span = led.marker_span
        self._fraction = led.hit_marker_fraction

        self._lives: dict[PlayerId, int] = {1: pong.lives, 2: pong.lives}
        self._from_player: PlayerId = pong.first_server  # type: ignore[assignment]
        self._to_player: PlayerId = _other(self._from_player)
        self._seg_start_ms = 0
        self._arrival_ms = 0
        self._from_index = 0
        self._to_index = 0
        self._end_index = 0
        self._direction = 1
        self._speed_leds_per_ms = 0.0
        self._ball_color: RgbPixel = WHITE
        self._returned = False
        self._auto_committed_miss = False
        self._speed_level = 1.0
        self._perfect_active = False
        self._state: PongState = "rally"
        self._pending_server: PlayerId = pong.first_server  # type: ignore[assignment]
        self._flash_color: RgbPixel = WHITE
        self._flash_side: PlayerId = 1
        self._flash_started_ms = 0
        self._flash_until_ms = 0
        self._feedback: list[_Feedback] = []

        self._perfect_count = 0
        self._good_count = 0
        self._miss_count = 0
        self._rally_count = 0
        self._abandoned = False
        self._empty_shutdown = EmptyShutdownTracker(threshold_ms=empty_shutdown_ms)

    def start(self) -> None:
        """Reset state and serve the first ball."""
        self._lives = {1: self._pong.lives, 2: self._pong.lives}
        self._feedback = []
        self._perfect_count = 0
        self._good_count = 0
        self._miss_count = 0
        self._rally_count = 0
        self._abandoned = False
        self._empty_shutdown = EmptyShutdownTracker(
            threshold_ms=self._empty_shutdown.threshold_ms,
        )
        self._speed_level = 1.0
        self._perfect_active = False
        self._serve(self._pong.first_server, now_ms=self._clock_ms())  # type: ignore[arg-type]

    def _index_of(self, player: PlayerId) -> int:
        return ball_index_for_player(
            player,
            strip_len=self._strip_len,
            span=self._marker_span,
            fraction=self._fraction,
        )

    def _travel_ms(self) -> int:
        perfect_factor = self._pong.perfect_multiplier if self._perfect_active else 1.0
        speed = max(self._speed_level * perfect_factor, 1e-6)
        return max(1, round(self._pong.base_travel_ms / speed))

    def _begin_segment(self, now_ms: int, *, is_serve: bool) -> None:
        self._seg_start_ms = now_ms
        self._from_index = self._index_of(self._from_player)
        self._to_index = self._index_of(self._to_player)
        # The ball travels past the receiver marker toward that player's end.
        self._end_index = 0 if self._to_player == 1 else self._strip_len - 1
        self._direction = 1 if self._to_index >= self._from_index else -1
        distance = abs(self._to_index - self._from_index)
        travel = self._travel_ms()
        self._arrival_ms = now_ms + travel
        self._speed_leds_per_ms = distance / travel if travel > 0 else float(distance)
        self._returned = False
        self._auto_committed_miss = False
        self._state = "rally"
        if is_serve:
            self._sfx.play("hit")

    def _serve(self, server: PlayerId, *, now_ms: int) -> None:
        self._from_player = server
        self._to_player = _other(server)
        self._speed_level = 1.0  # reset on each new serve / lost life
        self._perfect_active = False
        self._ball_color = WHITE
        self._begin_segment(now_ms, is_serve=True)

    def _ball_position(self, now_ms: int) -> float:
        elapsed = max(now_ms - self._seg_start_ms, 0)
        position = self._from_index + self._direction * elapsed * self._speed_leds_per_ms
        return min(max(position, 0.0), float(self._strip_len - 1))

    def _overshoot(self, now_ms: int) -> float:
        """LED distance the ball has travelled past the receiver marker (signed)."""
        return self._direction * (self._ball_position(now_ms) - self._to_index)

    def _return_ball(
        self,
        receiver: PlayerId,
        judgement: Judgement,
        now_ms: int,
    ) -> None:
        self._ball_color = PLAYER_COLORS[receiver]
        self._speed_level *= self._pong.continuous_multiplier
        self._perfect_active = judgement == Judgement.PERFECT
        self._rally_count += 1
        if judgement == Judgement.PERFECT:
            self._perfect_count += 1
            self._sfx.play("perfect")
        else:
            self._good_count += 1
            self._sfx.play("hit")
        self._feedback.append(
            _Feedback(player=receiver, judgement=judgement, started_ms=now_ms),
        )
        self._from_player = receiver
        self._to_player = _other(receiver)
        self._begin_segment(now_ms, is_serve=False)

    def _start_flash(
        self,
        *,
        color: RgbPixel,
        side: PlayerId,
        count: int,
        now_ms: int,
    ) -> None:
        self._flash_color = color
        self._flash_side = side
        self._flash_started_ms = now_ms
        self._flash_until_ms = now_ms + count * 2 * self._pong.flash_ms

    def _register_miss(self, receiver: PlayerId, now_ms: int) -> None:
        self._miss_count += 1
        self._lives[receiver] = max(0, self._lives[receiver] - 1)
        self._sfx.play("miss")
        self._returned = True
        winner = _other(receiver)
        winner_color = PLAYER_COLORS[winner]
        if self._lives[receiver] <= 0:
            self._state = "game_over"
            return
        self._pending_server = receiver
        self._start_flash(
            color=winner_color,
            side=winner,
            count=self._pong.point_flash_count,
            now_ms=now_ms,
        )
        self._state = "point_flash"

    def _prune_feedback(self, now_ms: int) -> None:
        self._feedback = [
            flash
            for flash in self._feedback
            if now_ms - flash.started_ms < self._led.hit_flash_ms
        ]

    def _handle_human_press(self, presses: ButtonPresses, now_ms: int) -> None:
        pressed = presses.p1 if self._to_player == 1 else presses.p2
        if not pressed:
            return
        distance = abs(self._ball_position(now_ms) - self._to_index)
        if distance <= self._pong.perfect_distance_leds:
            judgement = Judgement.PERFECT
        elif distance <= self._pong.good_distance_leds:
            judgement = Judgement.GOOD
        else:
            return  # mistimed press is ignored, no penalty
        self._return_ball(self._to_player, judgement, now_ms)

    def _ball_head_index(self, now_ms: int) -> int:
        if self._state in ("point_flash", "game_over"):
            return self._index_of(self._from_player)
        return round(self._ball_position(now_ms))

    def _flash_on(self, now_ms: int) -> bool:
        elapsed = max(now_ms - self._flash_started_ms, 0)
        return (elapsed // max(self._pong.flash_ms, 1)) % 2 == 0

    def tick(self) -> PongSnapshot:
        """Advance Pong by one frame and render it."""
        now_ms = self._clock_ms()
        self._prune_feedback(now_ms)

        # Always poll so button edge tracking stays current.
        presses = self._button_manager.poll()
        if self._empty_shutdown.update(
            self._button_manager.held_states(),
            now_ms=now_ms,
        ):
            self._abandoned = True

        if self._state == "point_flash":
            if now_ms >= self._flash_until_ms:
                self._serve(self._pending_server, now_ms=now_ms)
        elif self._state == "rally":
            if self._to_player in self._auto_players:
                if (
                    not self._returned
                    and not self._auto_committed_miss
                    and self._overshoot(now_ms) >= 0
                ):
                    if self._rng() < self._auto_miss_chance:
                        self._auto_committed_miss = True
                    else:
                        judgement = (
                            Judgement.PERFECT
                            if self._rng() < self._pong.auto_perfect_chance
                            else Judgement.GOOD
                        )
                        self._return_ball(self._to_player, judgement, now_ms)
            else:
                self._handle_human_press(presses, now_ms)

            if (
                self._state == "rally"
                and not self._returned
                and self._overshoot(now_ms) > self._pong.good_distance_leds
            ):
                self._register_miss(self._to_player, now_ms)

        self._render(now_ms)
        return self._snapshot(now_ms)

    def _render(self, now_ms: int) -> None:
        if self._state == "point_flash":
            color = self._flash_color if self._flash_on(now_ms) else OFF
            self._led_output.write_frame(
                build_half_flash_frame(
                    strip_len=self._strip_len,
                    color=color,
                    side=self._flash_side,
                ),
            )
            return

        if self._state == "game_over":
            self._led_output.write_frame(
                build_full_flash_frame(strip_len=self._strip_len, color=OFF),
            )
            return

        feedback = tuple(
            (flash.player, flash.judgement, now_ms - flash.started_ms)
            for flash in self._feedback
        )
        ball_visible = self._state != "game_over"
        frame = build_pong_frame(
            strip_len=self._strip_len,
            led=self._led,
            ball_head_index=self._ball_head_index(now_ms),
            ball_color=self._ball_color,
            ball_visible=ball_visible,
            ball_parked=False,
            travel_right_to_left=self._to_player == 1,
            feedback=feedback,
        )
        self._led_output.write_frame(frame)

    def _snapshot(self, now_ms: int) -> PongSnapshot:
        return PongSnapshot(
            now_ms=now_ms,
            state=self._state,
            lives_p1=self._lives[1],
            lives_p2=self._lives[2],
            ball_index=self._ball_head_index(now_ms),
            ball_color=self._ball_color,
            from_player=self._from_player,
            to_player=self._to_player,
            perfect_count=self._perfect_count,
            good_count=self._good_count,
            miss_count=self._miss_count,
            rally_count=self._rally_count,
            game_over=self._state == "game_over",
            abandoned=self._abandoned,
        )

    def _winner(self) -> PlayerId:
        p1_points = self._pong.lives - self._lives[2]
        p2_points = self._pong.lives - self._lives[1]
        return 1 if p1_points >= p2_points else 2

    def _run_end_sequence(self) -> None:
        """Segment score reveal followed by full-strip winner applause."""
        half_len = self._strip_len // 2
        segment_len = max(1, half_len // self._pong.lives)
        p1_points = self._pong.lives - self._lives[2]
        p2_points = self._pong.lives - self._lives[1]
        run_score_animation(
            led_output=self._led_output,
            sfx=self._sfx,
            strip_len=self._strip_len,
            p1_target=p1_points * segment_len,
            p2_target=p2_points * segment_len,
            step_ms=self._pong.score_step_ms,
            step_leds=segment_len,
            sleep=self._sleep,
        )
        winner = self._winner()
        winner_color = PLAYER_COLORS[winner]
        run_applause_animation(
            led_output=self._led_output,
            sfx=self._sfx,
            on_frame=build_full_flash_frame(
                strip_len=self._strip_len,
                color=winner_color,
            ),
            count=self._pong.gameover_flash_count,
            flash_ms=self._pong.flash_ms,
            sleep=self._sleep,
        )

    def run(self, *, max_duration_s: float | None = None) -> PongSnapshot:
        """Run the live loop until game over or an optional time limit."""
        tick_s = 1.0 / max(self._runtime.update_hz, 1)
        deadline = (
            time.monotonic() + max_duration_s
            if max_duration_s is not None
            else None
        )
        snapshot = self.tick()
        while not snapshot.game_over and not snapshot.abandoned:
            if deadline is not None and time.monotonic() >= deadline:
                break
            time.sleep(tick_s)
            snapshot = self.tick()
        if snapshot.game_over and not snapshot.abandoned:
            self._run_end_sequence()
        return snapshot
