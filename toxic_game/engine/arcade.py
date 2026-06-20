"""Always-on arcade dispatcher.

Renders a gentle idle screen and waits for a button press. A Player 1 press
launches Pong; a Player 2 press launches the rhythm jump game followed by its
end-of-song score reveal. Afterwards control returns to the idle screen.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from typing import Protocol

from toxic_game.config import (
    ArcadeConfig,
    GameplayConfig,
    LedConfig,
    PongConfig,
    RuntimeConfig,
)
from toxic_game.engine.button_manager import ButtonManager, ButtonPresses
from toxic_game.engine.game import GameManager
from toxic_game.engine.led_frames import (
    CYAN,
    MAGENTA,
    LedFrame,
    blank_pixels,
    build_frame,
    scale_pixel,
)
from toxic_game.engine.led_gameplay import MARKER_INTENSITY, hit_marker_range
from toxic_game.engine.notes import SongNotes
from toxic_game.engine.pong import PongManager
from toxic_game.engine.presence import HoldStartTracker, HeldStates
from toxic_game.engine.score_animation import (
    build_full_flash_frame,
    build_tie_applause_frame,
    leds_to_light,
    run_applause_animation,
    run_score_animation,
)
from toxic_game.engine.song_config import SongConfig
from toxic_game.engine.song_manager import SongManager
from toxic_game.hw.led_output import LedOutput
from toxic_game.hw.sfx import NoOpSfxPlayer, SfxPlayer

IDLE_BREATHE_PERIOD_MS = 2600
IDLE_BREATHE_FLOOR = 0.25


class ButtonPoller(Protocol):
    """Protocol for button polling sources used by the dispatcher."""

    def poll(self) -> ButtonPresses:
        """Return edge-triggered button presses for this tick."""

    def held_states(self) -> HeldStates:
        """Return whether each player's contact circuit is currently closed."""


def build_idle_frame(
    *,
    strip_len: int,
    led: LedConfig,
    phase_ms: int,
    period_ms: int = IDLE_BREATHE_PERIOD_MS,
) -> LedFrame:
    """Render breathing end markers (magenta left, cyan right)."""
    phase = (phase_ms % period_ms) / period_ms
    breathe = IDLE_BREATHE_FLOOR + (1.0 - IDLE_BREATHE_FLOOR) * (
        0.5 - 0.5 * math.cos(2.0 * math.pi * phase)
    )
    pixels = blank_pixels(strip_len)
    for player, color in ((1, MAGENTA), (2, CYAN)):
        start, end = hit_marker_range(
            player=player,  # type: ignore[arg-type]
            strip_len=strip_len,
            span=led.marker_span,
            fraction=led.hit_marker_fraction,
        )
        lit = scale_pixel(color, MARKER_INTENSITY * breathe)
        for index in range(start, end + 1):
            pixels[index] = lit
    return build_frame(pixels)


class ArcadeDispatcher:
    """Idle loop that launches Pong (P1) or rhythm jump (P2) on a press."""

    def __init__(
        self,
        *,
        button_manager: ButtonPoller,
        led_output: LedOutput,
        led: LedConfig,
        gameplay: GameplayConfig,
        pong: PongConfig,
        runtime: RuntimeConfig,
        arcade: ArcadeConfig,
        song: SongConfig | None = None,
        notes: SongNotes | None = None,
        song_manager: SongManager | None = None,
        pong_sfx: SfxPlayer | None = None,
        gameplay_sfx: SfxPlayer | None = None,
        clock_ms: Callable[[], int] | None = None,
        sleep: Callable[[float], None] | None = None,
        run_pong: Callable[[], None] | None = None,
        run_rhythm_jump: Callable[[], None] | None = None,
        run_demo: Callable[[], int | None] | None = None,
    ) -> None:
        self._buttons = button_manager
        self._led_output = led_output
        self._led = led
        self._gameplay = gameplay
        self._pong = pong
        self._runtime = runtime
        self._arcade = arcade
        self._song = song
        self._notes = notes
        self._song_manager = song_manager
        self._pong_sfx = pong_sfx or NoOpSfxPlayer()
        self._gameplay_sfx = gameplay_sfx or NoOpSfxPlayer()
        self._clock_ms = clock_ms or (lambda: int(time.monotonic() * 1000))
        self._sleep = sleep or time.sleep
        self._run_pong_impl = run_pong or self._default_run_pong
        self._run_rhythm_jump_impl = run_rhythm_jump or self._default_run_rhythm_jump
        self._run_demo_impl = run_demo or self._default_run_demo

        self._strip_len = led.active_count
        self._demo_idle_ms = arcade.demo_idle_s * 1000

    def render_idle(self) -> None:
        """Render one idle frame at the current clock phase."""
        self._led_output.write_frame(
            build_idle_frame(
                strip_len=self._strip_len,
                led=self._led,
                phase_ms=self._clock_ms(),
            ),
        )

    def _await_press(self) -> int:
        tick_s = 1.0 / max(self._runtime.update_hz, 1)
        hold_tracker = HoldStartTracker(start_hold_ms=self._arcade.start_hold_ms)
        idle_since_ms = self._clock_ms()
        while True:
            self.render_idle()
            now_ms = self._clock_ms()
            player = hold_tracker.update(
                self._buttons.held_states(),
                now_ms=now_ms,
            )
            if player is not None:
                return player
            if (
                self._demo_idle_ms > 0
                and now_ms - idle_since_ms >= self._demo_idle_ms
            ):
                player = self._run_demo_impl()
                if player is not None:
                    return player
                hold_tracker = HoldStartTracker(
                    start_hold_ms=self._arcade.start_hold_ms,
                )
                idle_since_ms = self._clock_ms()
            self._sleep(tick_s)

    def _default_run_pong(self) -> None:
        game = PongManager(
            button_manager=self._buttons,
            led_output=self._led_output,
            led=self._led,
            windows=self._gameplay.judgement_windows_ms,
            pong=self._pong,
            runtime=self._runtime,
            sfx=self._pong_sfx,
            empty_shutdown_ms=self._gameplay.empty_shutdown_s * 1000,
        )
        game.start()
        game.run()

    def _default_run_demo(self) -> int | None:
        """Run attract-mode Pong until interrupted or game over."""
        tick_s = 1.0 / max(self._runtime.update_hz, 1)
        self._pong_sfx.set_volume(self._arcade.demo_volume)
        try:
            game = PongManager(
                button_manager=self._buttons,
                led_output=self._led_output,
                led=self._led,
                windows=self._gameplay.judgement_windows_ms,
                pong=self._pong,
                runtime=self._runtime,
                sfx=self._pong_sfx,
                auto_players=frozenset({1, 2}),
                auto_miss_chance=self._arcade.demo_miss_chance,
                empty_shutdown_ms=self._gameplay.empty_shutdown_s * 1000,
                clock_ms=self._clock_ms,
                sleep=self._sleep,
            )
            game.start()
            hold_tracker = HoldStartTracker(
                start_hold_ms=self._arcade.start_hold_ms,
            )
            while True:
                snapshot = game.tick()
                now_ms = self._clock_ms()
                player = hold_tracker.update(
                    self._buttons.held_states(),
                    now_ms=now_ms,
                )
                if player is not None:
                    return player
                if snapshot.game_over:
                    return None
                self._sleep(tick_s)
        finally:
            self._pong_sfx.set_volume(1.0)

    def _default_run_rhythm_jump(self) -> None:
        if self._song is None or self._notes is None or self._song_manager is None:
            message = "rhythm jump requires song, notes, and a song manager"
            raise RuntimeError(message)
        self._song_manager.load(self._song)
        game = GameManager(
            song_manager=self._song_manager,
            button_manager=self._buttons,
            led_output=self._led_output,
            gameplay=self._gameplay,
            led=self._led,
            runtime=self._runtime,
            empty_shutdown_ms=self._gameplay.empty_shutdown_s * 1000,
            sfx=self._gameplay_sfx,
        )
        game.start(notes_p1=self._notes.player1, notes_p2=self._notes.player2)
        snapshot = game.run()
        if snapshot.abandoned:
            return
        p1_pct, p2_pct = game.final_percentages()
        half_len = self._strip_len // 2
        run_score_animation(
            led_output=self._led_output,
            sfx=self._gameplay_sfx,
            strip_len=self._strip_len,
            p1_target=leds_to_light(p1_pct, half_len),
            p2_target=leds_to_light(p2_pct, half_len),
            step_ms=self._gameplay.score_step_ms,
            sleep=self._sleep,
        )
        if p1_pct > p2_pct:
            applause_frame = build_full_flash_frame(
                strip_len=self._strip_len,
                color=MAGENTA,
            )
        elif p2_pct > p1_pct:
            applause_frame = build_full_flash_frame(
                strip_len=self._strip_len,
                color=CYAN,
            )
        else:
            applause_frame = build_tie_applause_frame(strip_len=self._strip_len)
        run_applause_animation(
            led_output=self._led_output,
            sfx=self._gameplay_sfx,
            on_frame=applause_frame,
            count=self._gameplay.applause_flash_count,
            flash_ms=self._gameplay.applause_flash_ms,
            sleep=self._sleep,
        )

    def run_once(self) -> int:
        """Wait for a press, launch the matching game, and return the player id."""
        player = self._await_press()
        if player == 1:
            self._run_pong_impl()
        else:
            self._run_rhythm_jump_impl()
        return player

    def run(self, *, max_launches: int | None = None) -> None:
        """Idle/launch loop. ``max_launches`` bounds iterations (tests)."""
        launches = 0
        while max_launches is None or launches < max_launches:
            self.run_once()
            launches += 1


__all__ = ["ArcadeDispatcher", "ButtonManager", "build_idle_frame"]
