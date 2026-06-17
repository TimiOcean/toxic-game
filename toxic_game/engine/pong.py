"""Pong game mode: a single bouncing running light between the two markers.

Reuses the rhythm game's input (:class:`ButtonManager`), scoring windows
(:func:`evaluate_press`), marker geometry, and LED output. The rhythm
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
from toxic_game.engine.led_frames import CYAN, MAGENTA, RgbPixel, WHITE
from toxic_game.engine.notes import ResolvedNote
from toxic_game.engine.pong_led import ball_index_for_player, build_pong_frame
from toxic_game.engine.scoring import Judgement, evaluate_press
from toxic_game.hw.led_output import LedOutput
from toxic_game.hw.sfx import NoOpSfxPlayer, SfxPlayer

PlayerId = Literal[1, 2]

PongState = Literal["rally", "serve_delay", "game_over"]

_PLAYER_COLORS: dict[PlayerId, RgbPixel] = {1: MAGENTA, 2: CYAN}


class ButtonPoller(Protocol):
    """Protocol for button polling sources used by the Pong manager."""

    def poll(self) -> ButtonPresses:
        """Return edge-triggered button presses for this tick."""


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
        clock_ms: Callable[[], int] | None = None,
        rng: Callable[[], float] | None = None,
    ) -> None:
        self._button_manager = button_manager or ButtonManager()
        self._led_output = led_output
        self._led = led
        self._windows = windows
        self._pong = pong
        self._runtime = runtime
        self._sfx = sfx or NoOpSfxPlayer()
        self._auto_players = auto_players
        self._clock_ms = clock_ms or (lambda: int(time.monotonic() * 1000))
        self._rng = rng or random.random

        self._strip_len = led.active_count
        self._span = led.running_light_span
        self._fraction = led.hit_marker_fraction

        self._lives: dict[PlayerId, int] = {1: pong.lives, 2: pong.lives}
        self._from_player: PlayerId = pong.first_server  # type: ignore[assignment]
        self._to_player: PlayerId = _other(self._from_player)
        self._seg_start_ms = 0
        self._arrival_ms = 0
        self._ball_color: RgbPixel = WHITE
        self._returned = False
        self._speed_level = 1.0
        self._perfect_active = False
        self._state: PongState = "serve_delay"
        self._serve_at_ms = 0
        self._pending_server: PlayerId = pong.first_server  # type: ignore[assignment]
        self._feedback: list[_Feedback] = []

        self._perfect_count = 0
        self._good_count = 0
        self._miss_count = 0
        self._rally_count = 0

    def start(self) -> None:
        """Reset state and serve the first ball."""
        self._lives = {1: self._pong.lives, 2: self._pong.lives}
        self._feedback = []
        self._perfect_count = 0
        self._good_count = 0
        self._miss_count = 0
        self._rally_count = 0
        self._speed_level = 1.0
        self._perfect_active = False
        self._serve(self._pong.first_server, now_ms=self._clock_ms())  # type: ignore[arg-type]

    def _index_of(self, player: PlayerId) -> int:
        return ball_index_for_player(
            player,
            strip_len=self._strip_len,
            span=self._span,
            fraction=self._fraction,
        )

    def _travel_ms(self) -> int:
        perfect_factor = self._pong.perfect_multiplier if self._perfect_active else 1.0
        speed = max(self._speed_level * perfect_factor, 1e-6)
        return max(1, round(self._pong.base_travel_ms / speed))

    def _begin_segment(self, now_ms: int, *, is_serve: bool) -> None:
        self._seg_start_ms = now_ms
        self._arrival_ms = now_ms + self._travel_ms()
        self._returned = False
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

    def _return_ball(
        self,
        receiver: PlayerId,
        judgement: Judgement,
        now_ms: int,
    ) -> None:
        self._ball_color = _PLAYER_COLORS[receiver]
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

    def _register_miss(self, receiver: PlayerId, now_ms: int) -> None:
        self._miss_count += 1
        self._lives[receiver] = max(0, self._lives[receiver] - 1)
        self._sfx.play("miss")
        self._feedback.append(
            _Feedback(player=receiver, judgement=Judgement.ERROR, started_ms=now_ms),
        )
        # Park the ball at the misser's side for the serve delay.
        self._from_player = receiver
        self._to_player = _other(receiver)
        self._ball_color = WHITE
        self._returned = True
        if self._lives[receiver] <= 0:
            self._state = "game_over"
            return
        self._pending_server = receiver
        self._serve_at_ms = now_ms + self._pong.serve_delay_ms
        self._state = "serve_delay"

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
        target = ResolvedNote(
            player=self._to_player,
            bar=1,
            beat=1,
            hit_ms=self._arrival_ms,
            spawn_ms=self._seg_start_ms,
        )
        result = evaluate_press(
            notes=(target,),
            press_ms=now_ms,
            windows=self._windows,
        )
        if result.judgement in (Judgement.PERFECT, Judgement.GOOD):
            self._return_ball(self._to_player, result.judgement, now_ms)

    def _ball_head_index(self, now_ms: int) -> int:
        from_index = self._index_of(self._from_player)
        to_index = self._index_of(self._to_player)
        if self._state != "rally":
            return from_index
        travel = max(self._arrival_ms - self._seg_start_ms, 1)
        ratio = (now_ms - self._seg_start_ms) / travel
        ratio = min(max(ratio, 0.0), 1.0)
        return round(from_index + (to_index - from_index) * ratio)

    def tick(self) -> PongSnapshot:
        """Advance Pong by one frame and render it."""
        now_ms = self._clock_ms()
        self._prune_feedback(now_ms)

        # Always poll so button edge tracking stays current.
        presses = self._button_manager.poll()

        if self._state == "serve_delay" and now_ms >= self._serve_at_ms:
            self._serve(self._pending_server, now_ms=now_ms)

        if self._state == "rally":
            if self._to_player in self._auto_players:
                if not self._returned and now_ms >= self._arrival_ms:
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
                and now_ms > self._arrival_ms + self._windows.good
            ):
                self._register_miss(self._to_player, now_ms)

        self._render(now_ms)
        return self._snapshot(now_ms)

    def _render(self, now_ms: int) -> None:
        feedback = tuple(
            (flash.player, flash.judgement, now_ms - flash.started_ms)
            for flash in self._feedback
        )
        ball_visible = self._state != "game_over"
        ball_parked = self._state == "serve_delay"
        frame = build_pong_frame(
            strip_len=self._strip_len,
            span=self._span,
            led=self._led,
            ball_head_index=self._ball_head_index(now_ms),
            ball_color=self._ball_color,
            ball_visible=ball_visible,
            ball_parked=ball_parked,
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
        while not snapshot.game_over:
            if deadline is not None and time.monotonic() >= deadline:
                break
            time.sleep(tick_s)
            snapshot = self.tick()
        return snapshot
