"""Main gameplay manager wiring song, input, scoring, health, and LEDs."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

from toxic_game.config import GameplayConfig, LedConfig, RuntimeConfig
from toxic_game.engine.button_manager import ButtonManager, ButtonPresses
from toxic_game.engine.health import HealthState, apply_judgement, make_health_state
from toxic_game.engine.led_gameplay import HitFeedback, build_gameplay_frame
from toxic_game.engine.notes import ResolvedNote
from toxic_game.engine.scoring import Judgement, evaluate_press, pop_missed_notes
from toxic_game.engine.song_manager import SongManager
from toxic_game.hw.led_output import LedOutput


class ButtonPoller(Protocol):
    """Protocol for button polling sources used by game manager."""

    def poll(self) -> ButtonPresses:
        """Return edge-triggered button presses for this tick."""


@dataclass(frozen=True, slots=True)
class GameSnapshot:
    """One tick of gameplay state."""

    position_ms: int
    health: int
    game_over: bool
    perfect_count: int
    good_count: int
    error_count: int
    pending_p1: int
    pending_p2: int


class GameManager:
    """Coordinate song time, input scoring, health, and LED output."""

    def __init__(
        self,
        *,
        song_manager: SongManager,
        button_manager: ButtonPoller | None,
        led_output: LedOutput,
        gameplay: GameplayConfig,
        led: LedConfig,
        runtime: RuntimeConfig,
        solo_mode: bool = False,
    ) -> None:
        self._song_manager = song_manager
        self._button_manager = button_manager or ButtonManager()
        self._led_output = led_output
        self._gameplay = gameplay
        self._led = led
        self._runtime = runtime
        self._solo_mode = solo_mode

        self._pending_p1: tuple[ResolvedNote, ...] = ()
        self._pending_p2: tuple[ResolvedNote, ...] = ()
        self._feedback: list[HitFeedback] = []
        self._health_state: HealthState = make_health_state(gameplay.health)
        self._perfect_count = 0
        self._good_count = 0
        self._error_count = 0
        self._game_over = False

    def start(
        self,
        *,
        notes_p1: tuple[ResolvedNote, ...],
        notes_p2: tuple[ResolvedNote, ...],
        start_ms: int = 0,
    ) -> None:
        """Start gameplay with the provided resolved notes."""
        self._pending_p1 = tuple(sorted(notes_p1, key=lambda note: note.hit_ms))
        self._pending_p2 = tuple(sorted(notes_p2, key=lambda note: note.hit_ms))
        self._feedback = []
        self._health_state = make_health_state(self._gameplay.health)
        self._perfect_count = 0
        self._good_count = 0
        self._error_count = 0
        self._game_over = False
        self._song_manager.play(start_ms=start_ms)

    def _prune_feedback(self, *, now_ms: int) -> None:
        self._feedback = [
            flash
            for flash in self._feedback
            if now_ms - flash.started_ms < self._led.hit_flash_ms
        ]

    def _add_feedback(
        self,
        *,
        player: int,
        judgement: Judgement,
        started_ms: int,
    ) -> None:
        self._feedback.append(
            HitFeedback(
                player=player,  # type: ignore[arg-type]
                started_ms=started_ms,
                judgement=judgement,
            ),
        )

    def _consume_misses(self, *, now_ms: int) -> None:
        self._pending_p1, missed_p1 = pop_missed_notes(
            notes=self._pending_p1,
            now_ms=now_ms,
            windows=self._gameplay.judgement_windows_ms,
        )
        self._pending_p2, missed_p2 = pop_missed_notes(
            notes=self._pending_p2,
            now_ms=now_ms,
            windows=self._gameplay.judgement_windows_ms,
        )
        for note in (*missed_p1, *missed_p2):
            self._add_feedback(
                player=note.player,
                judgement=Judgement.ERROR,
                started_ms=now_ms,
            )
            self._apply_judgement(Judgement.ERROR, player=note.player)

    def _apply_judgement(self, judgement: Judgement | None, *, player: int) -> None:
        if judgement == Judgement.PERFECT:
            self._perfect_count += 1
        elif judgement == Judgement.GOOD:
            self._good_count += 1
        elif judgement == Judgement.ERROR:
            self._error_count += 1

        if (
            self._solo_mode
            and player == 2
            and judgement == Judgement.ERROR
        ):
            return

        self._health_state = apply_judgement(
            state=self._health_state,
            judgement=judgement,
            config=self._gameplay.health,
        )
        self._game_over = self._health_state.is_game_over
        if self._game_over:
            self._song_manager.stop()

    def _handle_press(self, *, player: int, press_ms: int) -> None:
        pending = self._pending_p1 if player == 1 else self._pending_p2
        result = evaluate_press(
            notes=pending,
            press_ms=press_ms,
            windows=self._gameplay.judgement_windows_ms,
        )
        if result.matched_note is not None:
            filtered = tuple(note for note in pending if note != result.matched_note)
            if player == 1:
                self._pending_p1 = filtered
            else:
                self._pending_p2 = filtered
        if result.judgement is not None:
            self._add_feedback(
                player=player,
                judgement=result.judgement,
                started_ms=press_ms,
            )
            self._apply_judgement(result.judgement, player=player)

    def tick(self) -> GameSnapshot:
        """Advance gameplay by one frame."""
        now_ms = self._song_manager.position_ms
        self._prune_feedback(now_ms=now_ms)

        self._consume_misses(now_ms=now_ms)
        if not self._game_over:
            presses = self._button_manager.poll()
            if presses.p1:
                self._handle_press(player=1, press_ms=now_ms)
            if presses.p2:
                self._handle_press(player=2, press_ms=now_ms)

        frame = build_gameplay_frame(
            strip_len=self._led.active_count,
            span=self._led.running_light_span,
            progress_ms=now_ms,
            notes=(*self._pending_p1, *self._pending_p2),
            feedback=tuple(self._feedback),
            hit_flash_ms=self._led.hit_flash_ms,
        )
        self._led_output.write_frame(frame)
        return GameSnapshot(
            position_ms=now_ms,
            health=self._health_state.value,
            game_over=self._game_over,
            perfect_count=self._perfect_count,
            good_count=self._good_count,
            error_count=self._error_count,
            pending_p1=len(self._pending_p1),
            pending_p2=len(self._pending_p2),
        )

    def run(self, *, max_duration_s: float | None = None) -> GameSnapshot:
        """Run the live game loop until song end, game over, or max duration."""
        tick_s = 1.0 / max(self._runtime.update_hz, 1)
        deadline = (
            time.monotonic() + max_duration_s
            if max_duration_s is not None
            else None
        )
        snapshot = self.tick()
        while self._song_manager.is_playing and not snapshot.game_over:
            if deadline is not None and time.monotonic() >= deadline:
                break
            time.sleep(tick_s)
            snapshot = self.tick()
        return snapshot
