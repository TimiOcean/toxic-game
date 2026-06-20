"""Integration-style tests for GameManager tick orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from toxic_game.config import (
    GameplayConfig,
    HealthConfig,
    JudgementWindowsMs,
    LedConfig,
    RuntimeConfig,
    SfxConfig,
)
from toxic_game.engine.button_manager import ButtonPresses
from toxic_game.engine.game import GameManager
from toxic_game.engine.notes import ResolvedNote
from toxic_game.engine.presence import HeldStates
from toxic_game.hw.led_output import SimLedOutput
from toxic_game.hw.sfx import RecordingSfxPlayer


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

    @property
    def timing(self) -> None:
        return None


class ScriptedButtons:
    """Return predefined press states per tick."""

    def __init__(
        self,
        presses: list[ButtonPresses],
        *,
        held: HeldStates | None = None,
    ) -> None:
        self._presses = presses
        self._index = 0
        self._held = held or HeldStates(p1=False, p2=False)

    def poll(self) -> ButtonPresses:
        if self._index >= len(self._presses):
            return ButtonPresses(p1=False, p2=False)
        value = self._presses[self._index]
        self._index += 1
        return value

    def held_states(self) -> HeldStates:
        return self._held


def _note(*, player: int, hit_ms: int, spawn_ms: int = 0) -> ResolvedNote:
    return ResolvedNote(
        player=player,  # type: ignore[arg-type]
        bar=1,
        beat=1,
        hit_ms=hit_ms,
        spawn_ms=spawn_ms,
    )


def _sfx_config() -> SfxConfig:
    return SfxConfig(
        hit=None,
        perfect=None,
        miss=None,
        applause=None,
        chime=None,
        pitch_randomize=0.0,
    )


def _gameplay_config(*, duration_s: int = 60) -> GameplayConfig:
    return GameplayConfig(
        lead_time_beats=4,
        judgement_windows_ms=JudgementWindowsMs(perfect=20, good=50),
        health=HealthConfig(
            start=20,
            max=20,
            lose_on_error=2,
            gain_on_good=1,
            gain_on_perfect=2,
        ),
        duration_s=duration_s,
        score_perfect=3,
        score_good=1,
        score_step_ms=200,
        applause_flash_count=10,
        applause_flash_ms=150,
        empty_shutdown_s=5,
        sfx=_sfx_config(),
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
        hit_marker_fraction=0.10,
        running_light_spawn="end",
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
    # Perfect P1 hit triggers a white burst at the left end.
    assert led.frames[-1][0] == (255, 255, 255)

    song.position_ms = 1040
    game.tick()
    song.position_ms = 1300
    snapshot = game.tick()

    assert snapshot.perfect_count == 1
    assert snapshot.good_count == 1
    assert snapshot.error_count == 1
    assert snapshot.score_p1 == 3  # one perfect, miss costs nothing
    assert snapshot.score_p2 == 1  # one good
    assert snapshot.pending_p1 == 0
    assert snapshot.pending_p2 == 0
    assert len(led.frames) == 4


def test_perfect_hit_plays_perfect_sfx() -> None:
    song = ScriptedSongManager()
    buttons = ScriptedButtons([ButtonPresses(p1=True, p2=False)])
    sfx = RecordingSfxPlayer()
    game = GameManager(
        song_manager=song,  # type: ignore[arg-type]
        button_manager=buttons,  # type: ignore[arg-type]
        led_output=SimLedOutput(),
        gameplay=_gameplay_config(),
        led=_led_config(),
        runtime=RuntimeConfig(update_hz=60),
        sfx=sfx,
    )
    game.start(notes_p1=(_note(player=1, hit_ms=1000),), notes_p2=())
    song.position_ms = 1000
    game.tick()

    assert sfx.events == ["perfect"]


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

    assert snapshot.score_p1 == 0
    assert snapshot.score_p2 == 0
    assert snapshot.perfect_count == 0
    assert snapshot.good_count == 0
    assert snapshot.error_count == 0


def test_miss_never_ends_game() -> None:
    song = ScriptedSongManager()
    game = GameManager(
        song_manager=song,  # type: ignore[arg-type]
        button_manager=ScriptedButtons([ButtonPresses(p1=False, p2=False)]),  # type: ignore[arg-type]
        led_output=SimLedOutput(),
        gameplay=_gameplay_config(),
        led=_led_config(),
        runtime=RuntimeConfig(update_hz=60),
    )
    game.start(notes_p1=(_note(player=1, hit_ms=1000),), notes_p2=())
    song.position_ms = 1100
    snapshot = game.tick()

    assert snapshot.error_count == 1
    assert snapshot.score_p1 == 0
    assert snapshot.finished is False
    assert song.stop_called is False


def test_run_finishes_and_stops_song() -> None:
    song = ScriptedSongManager()
    game = GameManager(
        song_manager=song,  # type: ignore[arg-type]
        button_manager=ScriptedButtons([]),  # type: ignore[arg-type]
        led_output=SimLedOutput(),
        gameplay=_gameplay_config(),
        led=_led_config(),
        runtime=RuntimeConfig(update_hz=60),
    )
    game.start(notes_p1=(), notes_p2=())
    # Simulate the song reaching its natural end.
    song.is_playing = False
    snapshot = game.run()

    assert snapshot.finished is True
    assert song.stop_called is True


def test_final_percentages_capped_at_100() -> None:
    song = ScriptedSongManager()
    buttons = ScriptedButtons(
        [
            ButtonPresses(p1=True, p2=False),   # p1 good at 1040 on note 1000
            ButtonPresses(p1=False, p2=True),   # p2 perfect at 1000 on note 1000
        ],
    )
    game = GameManager(
        song_manager=song,  # type: ignore[arg-type]
        button_manager=buttons,  # type: ignore[arg-type]
        led_output=SimLedOutput(),
        gameplay=_gameplay_config(),
        led=_led_config(),
        runtime=RuntimeConfig(update_hz=60),
    )
    game.start(
        notes_p1=(_note(player=1, hit_ms=1000), _note(player=1, hit_ms=5000)),
        notes_p2=(_note(player=2, hit_ms=1000),),
    )
    song.position_ms = 1040
    game.tick()  # p1 good (40ms off note 1000)
    song.position_ms = 1000
    # Re-target p2: its note is at 1000.
    game.tick()  # p2 perfect

    p1_pct, p2_pct = game.final_percentages()
    assert p1_pct == 17   # 1 good of 2 notes -> 100*1/(2*3)
    assert p2_pct == 100  # 1 perfect of 1 note -> capped at 100


def test_abandons_when_both_pads_empty_for_threshold() -> None:
    song = ScriptedSongManager()
    clock = [0]
    buttons = ScriptedButtons(
        [],
        held=HeldStates(p1=False, p2=False),
    )
    game = GameManager(
        song_manager=song,  # type: ignore[arg-type]
        button_manager=buttons,  # type: ignore[arg-type]
        led_output=SimLedOutput(),
        gameplay=_gameplay_config(),
        led=_led_config(),
        runtime=RuntimeConfig(update_hz=60),
        empty_shutdown_ms=5000,
        clock_ms=lambda: clock[0],
    )
    game.start(notes_p1=(), notes_p2=())
    song.is_playing = True

    clock[0] = 0
    assert game.tick().abandoned is False
    clock[0] = 4999
    assert game.tick().abandoned is False
    clock[0] = 5000
    snapshot = game.tick()
    assert snapshot.abandoned is True
