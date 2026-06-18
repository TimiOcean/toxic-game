"""Main gameplay manager wiring song, input, score, and LEDs.

The rhythm jump game is score-based: 3 points for a perfect hit, 1 for a good
hit (configurable). There is no shared health and no game over; the match ends
after a fixed duration or when the song finishes.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from toxic_game.config import GameplayConfig, LedConfig, RuntimeConfig
from toxic_game.engine.button_manager import ButtonManager, ButtonPresses
from toxic_game.engine.led_gameplay import HitFeedback, build_gameplay_frame, feedback_duration_ms
from toxic_game.engine.notes import ResolvedNote
from toxic_game.engine.presence import EmptyShutdownTracker, HeldStates
from toxic_game.engine.score_animation import score_percentage
from toxic_game.engine.scoring import Judgement, evaluate_press, pop_missed_notes
from toxic_game.engine.song_manager import SongManager
from toxic_game.hw.led_output import LedOutput


class ButtonPoller(Protocol):
    """Protocol for button polling sources used by game manager."""

    def poll(self) -> ButtonPresses:
        """Return edge-triggered button presses for this tick."""

    def held_states(self) -> HeldStates:
        """Return whether each player's contact circuit is currently closed."""


@dataclass(frozen=True, slots=True)
class GameSnapshot:
    """One tick of gameplay state."""

    position_ms: int
    score_p1: int
    score_p2: int
    finished: bool
    perfect_count: int
    good_count: int
    error_count: int
    pending_p1: int
    pending_p2: int
    abandoned: bool


class GameManager:
    """Coordinate song time, input scoring, and LED output."""

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
        empty_shutdown_ms: int = 5000,
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        self._song_manager = song_manager
        self._button_manager = button_manager or ButtonManager()
        self._led_output = led_output
        self._gameplay = gameplay
        self._led = led
        self._runtime = runtime
        self._solo_mode = solo_mode
        self._clock_ms = clock_ms or (lambda: int(time.monotonic() * 1000))

        self._pending_p1: tuple[ResolvedNote, ...] = ()
        self._pending_p2: tuple[ResolvedNote, ...] = ()
        self._feedback: list[HitFeedback] = []
        self._score: dict[int, int] = {1: 0, 2: 0}
        self._perfect: dict[int, int] = {1: 0, 2: 0}
        self._good: dict[int, int] = {1: 0, 2: 0}
        self._error_count = 0
        self._total_p1 = 0
        self._total_p2 = 0
        self._finished = False
        self._abandoned = False
        self._empty_shutdown = EmptyShutdownTracker(threshold_ms=empty_shutdown_ms)

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
        self._total_p1 = len(self._pending_p1)
        self._total_p2 = len(self._pending_p2)
        self._feedback = []
        self._score = {1: 0, 2: 0}
        self._perfect = {1: 0, 2: 0}
        self._good = {1: 0, 2: 0}
        self._error_count = 0
        self._finished = False
        self._abandoned = False
        self._empty_shutdown = EmptyShutdownTracker(
            threshold_ms=self._empty_shutdown.threshold_ms,
        )
        self._song_manager.play(start_ms=start_ms)

    def _prune_feedback(self, *, now_ms: int) -> None:
        self._feedback = [
            flash
            for flash in self._feedback
            if now_ms - flash.started_ms < feedback_duration_ms(flash, self._led)
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
            # Misses keep the red feedback flash but do not change the score.
            self._add_feedback(
                player=note.player,
                judgement=Judgement.ERROR,
                started_ms=now_ms,
            )
            self._error_count += 1

    def _apply_judgement(self, judgement: Judgement | None, *, player: int) -> None:
        if judgement == Judgement.PERFECT:
            self._perfect[player] += 1
            self._score[player] += self._gameplay.score_perfect
        elif judgement == Judgement.GOOD:
            self._good[player] += 1
            self._score[player] += self._gameplay.score_good
        elif judgement == Judgement.ERROR:
            self._error_count += 1

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

    def _snapshot(self, now_ms: int) -> GameSnapshot:
        return GameSnapshot(
            position_ms=now_ms,
            score_p1=self._score[1],
            score_p2=self._score[2],
            finished=self._finished,
            perfect_count=self._perfect[1] + self._perfect[2],
            good_count=self._good[1] + self._good[2],
            error_count=self._error_count,
            pending_p1=len(self._pending_p1),
            pending_p2=len(self._pending_p2),
            abandoned=self._abandoned,
        )

    def tick(self) -> GameSnapshot:
        """Advance gameplay by one frame."""
        now_ms = self._song_manager.position_ms
        self._prune_feedback(now_ms=now_ms)

        if self._empty_shutdown.update(
            self._button_manager.held_states(),
            now_ms=self._clock_ms(),
        ):
            self._abandoned = True

        self._consume_misses(now_ms=now_ms)
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
            led=self._led,
            timing=self._song_manager.timing,
        )
        self._led_output.write_frame(frame)
        return self._snapshot(now_ms)

    def final_percentages(self) -> tuple[int, int]:
        """Return the (player 1, player 2) score percentages, each capped at 100."""
        p1 = score_percentage(
            perfect=self._perfect[1],
            good=self._good[1],
            total_notes=self._total_p1,
            score_perfect=self._gameplay.score_perfect,
            score_good=self._gameplay.score_good,
        )
        p2 = score_percentage(
            perfect=self._perfect[2],
            good=self._good[2],
            total_notes=self._total_p2,
            score_perfect=self._gameplay.score_perfect,
            score_good=self._gameplay.score_good,
        )
        return (p1, p2)

    def run(self, *, max_duration_s: float | None = None) -> GameSnapshot:
        """Run the live game loop until song end or the configured duration."""
        tick_s = 1.0 / max(self._runtime.update_hz, 1)
        duration = (
            max_duration_s
            if max_duration_s is not None
            else float(self._gameplay.duration_s)
        )
        deadline = time.monotonic() + duration if duration > 0 else None
        snapshot = self.tick()
        while self._song_manager.is_playing and not snapshot.abandoned:
            if deadline is not None and time.monotonic() >= deadline:
                break
            time.sleep(tick_s)
            snapshot = self.tick()
        self._finished = True
        self._song_manager.stop()
        return self._snapshot(snapshot.position_ms)
