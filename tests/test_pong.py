"""Tests for the Pong game mode."""

from __future__ import annotations

from toxic_game.config import (
    GpioConfig,
    JudgementWindowsMs,
    JumppadConfig,
    LedConfig,
    PongConfig,
    RuntimeConfig,
    SfxConfig,
)
from toxic_game.engine.button_manager import ButtonManager, SimButtonReader
from toxic_game.engine.led_frames import CYAN, WHITE
from toxic_game.engine.pong import PongManager
from toxic_game.hw.led_output import SimLedOutput
from toxic_game.hw.sfx import RecordingSfxPlayer


def _button_gpio_config() -> GpioConfig:
    return GpioConfig(
        left_contact_pin=17,
        right_contact_pin=27,
        debounce_ms=0,
        p1_input="button",
        p2_input="button",
        jumppad=JumppadConfig(min_air_ms=200, retrigger_ms=400),
    )


def _led_config(**overrides: object) -> LedConfig:
    defaults = {
        "muted_rgb_count": 0,
        "rgbw_count": 30,
        "pin": 18,
        "freq_hz": 800000,
        "dma": 10,
        "invert": False,
        "brightness": 255,
        "channel": 0,
        "hit_flash_ms": 200,
        "running_light_span": 2,
        "rgbw_byte_order": "WRGB",
        "hit_marker_fraction": 0.10,
        "running_light_spawn": "end",
    }
    defaults.update(overrides)
    return LedConfig(**defaults)  # type: ignore[arg-type]


def _pong_config(**overrides: object) -> PongConfig:
    defaults = {
        "base_travel_ms": 1000,
        "continuous_multiplier": 2.0,
        "perfect_multiplier": 2.0,
        "serve_delay_ms": 500,
        "lives": 3,
        "first_server": 1,
        "auto_perfect_chance": 0.10,
        "sfx": SfxConfig(hit=None, perfect=None, miss=None, pitch_randomize=0.0),
    }
    defaults.update(overrides)
    return PongConfig(**defaults)  # type: ignore[arg-type]


def _windows() -> JudgementWindowsMs:
    return JudgementWindowsMs(perfect=50, good=150)


class _ManualClock:
    def __init__(self) -> None:
        self.now = 0

    def __call__(self) -> int:
        return self.now


def _make_manager(
    *,
    clock: _ManualClock,
    reader: SimButtonReader,
    sfx: RecordingSfxPlayer | None = None,
    auto_players: frozenset[int] = frozenset(),
    rng: object | None = None,
    pong: PongConfig | None = None,
) -> tuple[PongManager, SimLedOutput]:
    led_output = SimLedOutput()
    buttons = ButtonManager(
        reader=reader,
        debounce_ms=0,
        clock_ms=lambda: clock.now,
        gpio_config=_button_gpio_config(),
    )
    manager = PongManager(
        button_manager=buttons,
        led_output=led_output,
        led=_led_config(),
        windows=_windows(),
        pong=pong or _pong_config(),
        runtime=RuntimeConfig(update_hz=60),
        sfx=sfx,
        auto_players=auto_players,  # type: ignore[arg-type]
        clock_ms=lambda: clock.now,
        rng=rng,  # type: ignore[arg-type]
    )
    return manager, led_output


def test_first_serve_is_neutral_white_and_plays_hit_sfx() -> None:
    clock = _ManualClock()
    reader = SimButtonReader({"left": False, "right": False})
    sfx = RecordingSfxPlayer()
    manager, _ = _make_manager(clock=clock, reader=reader, sfx=sfx)

    manager.start()
    snapshot = manager.tick()

    assert snapshot.state == "rally"
    assert snapshot.from_player == 1
    assert snapshot.to_player == 2
    assert snapshot.ball_color == WHITE
    assert sfx.events == ["hit"]  # serve uses the hit sfx


def test_ball_turns_receiver_color_on_hit() -> None:
    clock = _ManualClock()
    reader = SimButtonReader({"left": False, "right": False})
    manager, _ = _make_manager(clock=clock, reader=reader)
    manager.start()

    # Ball arrives at P2 marker after base_travel_ms (1000) at speed 1.
    clock.now = 1000
    reader.states["right"] = True
    snapshot = manager.tick()

    assert snapshot.ball_color == CYAN
    assert snapshot.to_player == 1  # now traveling back to P1
    assert snapshot.good_count + snapshot.perfect_count == 1


def test_perfect_hit_plays_perfect_sfx_and_speeds_up_next_traversal_only() -> None:
    clock = _ManualClock()
    reader = SimButtonReader({"left": False, "right": False})
    sfx = RecordingSfxPlayer()
    manager, _ = _make_manager(clock=clock, reader=reader, sfx=sfx)
    manager.start()

    # Perfect return by P2 exactly on arrival.
    clock.now = 1000
    reader.states["right"] = True
    manager.tick()

    assert "perfect" in sfx.events
    # continuous(2.0) * perfect(2.0) -> travel 1000/4 = 250ms back to P1.
    assert manager._arrival_ms - manager._seg_start_ms == 250  # noqa: SLF001

    # P1 returns (good, pressing 100 ms late); perfect bonus gone.
    reader.states["right"] = False
    clock.now = 1350
    reader.states["left"] = True
    manager.tick()
    # speed_level now 2*2 = 4, no perfect factor -> 1000/4 = 250ms.
    assert manager._arrival_ms - manager._seg_start_ms == 250  # noqa: SLF001


def test_miss_costs_a_life_and_resets_speed_on_serve() -> None:
    clock = _ManualClock()
    reader = SimButtonReader({"left": False, "right": False})
    sfx = RecordingSfxPlayer()
    manager, _ = _make_manager(clock=clock, reader=reader, sfx=sfx)
    manager.start()

    # P2 never presses; ball passes marker + good window -> miss.
    clock.now = 1000 + 150 + 1
    snapshot = manager.tick()

    assert snapshot.lives_p2 == 2
    assert snapshot.miss_count == 1
    assert snapshot.state == "serve_delay"
    assert "miss" in sfx.events

    # After serve delay, misser (P2) serves; speed reset to base.
    clock.now += 500
    snapshot = manager.tick()
    assert snapshot.state == "rally"
    assert snapshot.from_player == 2
    assert snapshot.to_player == 1
    assert manager._arrival_ms - manager._seg_start_ms == 1000  # noqa: SLF001 base speed


def test_mistimed_press_is_ignored() -> None:
    clock = _ManualClock()
    reader = SimButtonReader({"left": False, "right": False})
    manager, _ = _make_manager(clock=clock, reader=reader)
    manager.start()

    # Press way too early (outside good window) -> ignored, no return.
    clock.now = 200
    reader.states["right"] = True
    snapshot = manager.tick()

    assert snapshot.good_count == 0
    assert snapshot.perfect_count == 0
    assert snapshot.to_player == 2  # still traveling toward P2


def test_game_over_when_a_player_runs_out_of_lives() -> None:
    clock = _ManualClock()
    reader = SimButtonReader({"left": False, "right": False})
    manager, _ = _make_manager(clock=clock, reader=reader)
    manager.start()

    snapshot = manager.tick()
    for _ in range(20):  # nobody ever presses; misses alternate sides
        clock.now = manager._arrival_ms + 150 + 1  # noqa: SLF001 force a miss
        snapshot = manager.tick()
        if snapshot.game_over:
            break
        clock.now += 500  # wait out serve delay
        manager.tick()

    assert snapshot.game_over is True
    assert snapshot.state == "game_over"
    assert min(snapshot.lives_p1, snapshot.lives_p2) == 0


def test_solo_auto_player_always_returns() -> None:
    clock = _ManualClock()
    reader = SimButtonReader({"left": False, "right": False})
    # rng always 1.0 -> never perfect, always good.
    manager, _ = _make_manager(
        clock=clock,
        reader=reader,
        auto_players=frozenset({2}),
        rng=lambda: 1.0,
    )
    manager.start()

    clock.now = 1000
    snapshot = manager.tick()

    assert snapshot.lives_p2 == 3  # auto never misses
    assert snapshot.good_count == 1
    assert snapshot.ball_color == CYAN


def test_solo_auto_player_perfect_chance() -> None:
    clock = _ManualClock()
    reader = SimButtonReader({"left": False, "right": False})
    # rng 0.0 < 0.10 -> perfect.
    manager, _ = _make_manager(
        clock=clock,
        reader=reader,
        auto_players=frozenset({2}),
        rng=lambda: 0.0,
    )
    manager.start()

    clock.now = 1000
    snapshot = manager.tick()

    assert snapshot.perfect_count == 1


def test_demo_mode_both_auto_rallies_without_miss() -> None:
    clock = _ManualClock()
    reader = SimButtonReader({"left": False, "right": False})
    manager, _ = _make_manager(
        clock=clock,
        reader=reader,
        auto_players=frozenset({1, 2}),
        rng=lambda: 1.0,
    )
    manager.start()

    # Step through several arrivals; both sides auto-return.
    for _ in range(6):
        clock.now = manager._arrival_ms  # noqa: SLF001
        manager.tick()

    assert manager._lives[1] == 3  # noqa: SLF001
    assert manager._lives[2] == 3  # noqa: SLF001
    snapshot = manager.tick()
    assert snapshot.rally_count >= 5
    assert snapshot.game_over is False
