"""Integration-style tests for GameManager tick orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from toxic_game.config import (
    GameplayConfig,
    HealthConfig,
    JudgementWindowsMs,
    LedConfig,
    RuntimeConfig,
)
from toxic_game.engine.button_manager import ButtonPresses
from toxic_game.engine.game import GameManager
from toxic_game.engine.notes import ResolvedNote
from toxic_game.engine.led_frames import WHITE
from toxic_game.hw.led_output import SimLedOutput


@dataclass
class ScriptedSongManager:
    """Minimal song manager stub for deterministic game ticks."""

    position_ms: int = 0
    is_playing: bool = False
    stop_called: bool = False

    def play(self, *, start_ms: int = 0) -> None:
        self.position_ms = start_ms
        self.is_playing = True

    def stop(self) -> None:
        self.stop_called = True
        self.is_playing = False


class ScriptedButtons:
    """Return predefined press states per tick."""

    def __init__(self, presses: list[ButtonPresses]) -> None:
        self._presses = presses
        self._index = 0

    def poll(self) -> ButtonPresses:
        if self._index >= len(self._presses):
            return ButtonPresses(p1=False, p2=False)
        value = self._presses[self._index]
        self._index += 1
        return value


def _note(*, player: int, hit_ms: int, spawn_ms: int = 0) -> ResolvedNote:
    return ResolvedNote(
        player=player,  # type: ignore[arg-type]
        bar=1,
        beat=1,
        hit_ms=hit_ms,
        spawn_ms=spawn_ms,
    )


def _gameplay_config(*, start_health: int = 20) -> GameplayConfig:
    return GameplayConfig(
        lead_time_beats=4,
        judgement_windows_ms=JudgementWindowsMs(perfect=20, good=50),
        health=HealthConfig(
            start=start_health,
            max=20,
            lose_on_error=2,
            gain_on_good=1,
            gain_on_perfect=2,
        ),
    )


def _led_config() -> LedConfig:
    return LedConfig(
        muted_rgb_count=0,
        rgbw_count=10,
        pin=18,
        freq_hz=800000,
        dma=10,
        invert=False,
        brightness=255,
        channel=0,
        hit_flash_ms=180,
        running_light_span=2,
        rgbw_byte_order="WRGB",
    )


def test_tick_scores_presses_and_misses() -> None:
    song = ScriptedSongManager()
    buttons = ScriptedButtons(
        [
            ButtonPresses(p1=False, p2=False),
            ButtonPresses(p1=True, p2=False),   # perfect for p1 at 1000
            ButtonPresses(p1=False, p2=True),   # good for p2 at 1000 (press 1040)
            ButtonPresses(p1=False, p2=False),  # miss p1 note at 1200 once now=1300
        ],
    )
    led = SimLedOutput()
    game = GameManager(
        song_manager=song,  # type: ignore[arg-type]
        button_manager=buttons,  # type: ignore[arg-type]
        led_output=led,
        gameplay=_gameplay_config(),
        led=_led_config(),
        runtime=RuntimeConfig(update_hz=60),
    )
    game.start(
        notes_p1=(_note(player=1, hit_ms=1000), _note(player=1, hit_ms=1200)),
        notes_p2=(_note(player=2, hit_ms=1000),),
    )

    song.position_ms = 950
    game.tick()
    song.position_ms = 1000
    game.tick()
    assert led.frames[-1][0] == WHITE

    song.position_ms = 1040
    game.tick()
    song.position_ms = 1300
    snapshot = game.tick()

    assert snapshot.perfect_count == 1
    assert snapshot.good_count == 1
    assert snapshot.error_count == 1
    assert snapshot.health == 18
    assert snapshot.pending_p1 == 0
    assert snapshot.pending_p2 == 0
    assert len(led.frames) == 4


def test_ghost_tap_is_ignored_in_game_loop() -> None:
    song = ScriptedSongManager()
    buttons = ScriptedButtons([ButtonPresses(p1=True, p2=False)])
    game = GameManager(
        song_manager=song,  # type: ignore[arg-type]
        button_manager=buttons,  # type: ignore[arg-type]
        led_output=SimLedOutput(),
        gameplay=_gameplay_config(),
        led=_led_config(),
        runtime=RuntimeConfig(update_hz=60),
    )
    game.start(notes_p1=(), notes_p2=())
    song.position_ms = 500
    snapshot = game.tick()

    assert snapshot.health == 20
    assert snapshot.perfect_count == 0
    assert snapshot.good_count == 0
    assert snapshot.error_count == 0


def test_game_over_stops_song() -> None:
    song = ScriptedSongManager()
    game = GameManager(
        song_manager=song,  # type: ignore[arg-type]
        button_manager=ScriptedButtons([ButtonPresses(p1=False, p2=False)]),  # type: ignore[arg-type]
        led_output=SimLedOutput(),
        gameplay=_gameplay_config(start_health=2),
        led=_led_config(),
        runtime=RuntimeConfig(update_hz=60),
    )
    game.start(notes_p1=(_note(player=1, hit_ms=1000),), notes_p2=())
    song.position_ms = 1100
    snapshot = game.tick()

    assert snapshot.game_over is True
    assert snapshot.health == 0
    assert song.stop_called is True
