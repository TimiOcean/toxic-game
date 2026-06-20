"""Tests for the arcade dispatcher routing and idle frame."""

from __future__ import annotations

from toxic_game.config import (
    ArcadeConfig,
    GameplayConfig,
    HealthConfig,
    JudgementWindowsMs,
    LedConfig,
    PongConfig,
    RuntimeConfig,
    SfxConfig,
)
from toxic_game.engine.arcade import ArcadeDispatcher, build_idle_frame
from toxic_game.engine.button_manager import ButtonPresses
from toxic_game.engine.led_frames import OFF
from toxic_game.engine.presence import HeldStates
from toxic_game.hw.led_output import SimLedOutput


def _sfx_config() -> SfxConfig:
    return SfxConfig(
        hit=None,
        perfect=None,
        miss=None,
        applause=None,
        chime=None,
        pitch_randomize=0.0,
    )


def _led_config() -> LedConfig:
    return LedConfig(
        muted_rgb_count=0,
        rgbw_count=20,
        pin=18,
        freq_hz=800000,
        dma=10,
        invert=False,
        brightness=255,
        channel=0,
        hit_flash_ms=200,
        running_light_span=2,
        rgbw_byte_order="WRGB",
        hit_marker_fraction=0.10,
        running_light_spawn="end",
    )


def _gameplay_config() -> GameplayConfig:
    return GameplayConfig(
        lead_time_beats=4,
        judgement_windows_ms=JudgementWindowsMs(perfect=20, good=50),
        health=HealthConfig(start=20, max=20, lose_on_error=2, gain_on_good=1, gain_on_perfect=2),
        duration_s=60,
        score_perfect=3,
        score_good=1,
        score_step_ms=200,
        applause_flash_count=10,
        applause_flash_ms=150,
        empty_shutdown_s=5,
        sfx=_sfx_config(),
    )


def _pong_config() -> PongConfig:
    return PongConfig(
        base_travel_ms=1000,
        continuous_multiplier=1.05,
        perfect_multiplier=1.3,
        serve_delay_ms=500,
        lives=3,
        first_server=1,
        auto_perfect_chance=0.10,
        perfect_distance_leds=1,
        good_distance_leds=4,
        point_flash_count=5,
        point_flash_intensity=0.15,
        gameover_flash_count=10,
        flash_ms=150,
        sfx=_sfx_config(),
    )


class _FixedHoldPoller:
    def __init__(self, held: HeldStates) -> None:
        self._held = held

    def poll(self) -> ButtonPresses:
        return ButtonPresses(p1=False, p2=False)

    def held_states(self) -> HeldStates:
        return self._held


class _TimedHoldPoller:
    def __init__(self, clock: list[int]) -> None:
        self._clock = clock

    def poll(self) -> ButtonPresses:
        return ButtonPresses(p1=False, p2=False)

    def held_states(self) -> HeldStates:
        if self._clock[0] < 200:
            return HeldStates(p1=True, p2=False)
        return HeldStates(p1=False, p2=False)


def _make_dispatcher(
    *,
    poller: _FixedHoldPoller | _TimedHoldPoller,
    led_output: SimLedOutput,
    calls: list[str],
    clock: list[int] | None = None,
    start_hold_ms: int = 500,
) -> ArcadeDispatcher:
    clock_box = clock if clock is not None else [0]

    def advance(_seconds: float) -> None:
        clock_box[0] += 100

    return ArcadeDispatcher(
        button_manager=poller,
        led_output=led_output,
        led=_led_config(),
        gameplay=_gameplay_config(),
        pong=_pong_config(),
        runtime=RuntimeConfig(update_hz=60),
        arcade=ArcadeConfig(start_hold_ms=start_hold_ms),
        clock_ms=lambda: clock_box[0],
        sleep=advance,
        run_pong=lambda: calls.append("pong"),
        run_rhythm_jump=lambda: calls.append("rhythm"),
    )


def test_p1_sustained_hold_launches_pong() -> None:
    calls: list[str] = []
    clock = [0]
    poller = _FixedHoldPoller(HeldStates(p1=True, p2=False))
    dispatcher = _make_dispatcher(
        poller=poller,
        led_output=SimLedOutput(),
        calls=calls,
        clock=clock,
    )

    player = dispatcher.run_once()

    assert player == 1
    assert calls == ["pong"]
    assert clock[0] >= 500


def test_p2_sustained_hold_launches_rhythm_jump() -> None:
    calls: list[str] = []
    clock = [0]
    poller = _FixedHoldPoller(HeldStates(p1=False, p2=True))
    dispatcher = _make_dispatcher(
        poller=poller,
        led_output=SimLedOutput(),
        calls=calls,
        clock=clock,
    )

    player = dispatcher.run_once()

    assert player == 2
    assert calls == ["rhythm"]


def test_short_hold_does_not_launch() -> None:
    from toxic_game.engine.presence import HoldStartTracker

    tracker = HoldStartTracker(start_hold_ms=500)
    assert tracker.update(HeldStates(p1=True, p2=False), now_ms=0) is None
    assert tracker.update(HeldStates(p1=False, p2=False), now_ms=200) is None


def test_run_returns_to_idle_between_launches() -> None:
    calls: list[str] = []
    launches = iter(
        [
            _FixedHoldPoller(HeldStates(p1=True, p2=False)),
            _FixedHoldPoller(HeldStates(p1=False, p2=True)),
        ],
    )
    clock = [0]

    def advance(_seconds: float) -> None:
        clock[0] += 100

    dispatcher = ArcadeDispatcher(
        button_manager=next(launches),
        led_output=SimLedOutput(),
        led=_led_config(),
        gameplay=_gameplay_config(),
        pong=_pong_config(),
        runtime=RuntimeConfig(update_hz=60),
        arcade=ArcadeConfig(start_hold_ms=100),
        clock_ms=lambda: clock[0],
        sleep=advance,
        run_pong=lambda: calls.append("pong"),
        run_rhythm_jump=lambda: calls.append("rhythm"),
    )
    clock[0] = 0
    assert dispatcher.run_once() == 1
    clock[0] = 0
    dispatcher._buttons = next(launches)  # noqa: SLF001
    assert dispatcher.run_once() == 2
    assert calls == ["pong", "rhythm"]


def test_idle_renders_breathing_markers() -> None:
    led_output = SimLedOutput()
    dispatcher = _make_dispatcher(
        poller=_FixedHoldPoller(HeldStates(p1=False, p2=False)),
        led_output=led_output,
        calls=[],
    )

    dispatcher.render_idle()

    expected = build_idle_frame(
        strip_len=20,
        span=2,
        led=_led_config(),
        phase_ms=0,
    )
    assert led_output.frames[-1] == expected.pixels


def test_idle_frame_lights_only_markers() -> None:
    frame = build_idle_frame(strip_len=20, span=2, led=_led_config(), phase_ms=0)
    lit = [index for index, pixel in enumerate(frame.pixels) if pixel != OFF]

    assert len(lit) == 4
    assert min(lit) < 5
    assert max(lit) > 14
