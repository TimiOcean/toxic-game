"""Tests for the arcade dispatcher routing and idle frame."""

from __future__ import annotations

from toxic_game.config import (
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


class _ScriptedPoller:
    def __init__(self, scripted: list[ButtonPresses]) -> None:
        self._scripted = scripted
        self._index = 0

    def poll(self) -> ButtonPresses:
        if self._index < len(self._scripted):
            value = self._scripted[self._index]
            self._index += 1
            return value
        return ButtonPresses(p1=False, p2=False)


def _make_dispatcher(
    *,
    poller: _ScriptedPoller,
    led_output: SimLedOutput,
    calls: list[str],
) -> ArcadeDispatcher:
    return ArcadeDispatcher(
        button_manager=poller,
        led_output=led_output,
        led=_led_config(),
        gameplay=_gameplay_config(),
        pong=_pong_config(),
        runtime=RuntimeConfig(update_hz=60),
        clock_ms=lambda: 0,
        sleep=lambda _: None,
        run_pong=lambda: calls.append("pong"),
        run_rhythm_jump=lambda: calls.append("rhythm"),
    )


def test_p1_press_launches_pong() -> None:
    calls: list[str] = []
    poller = _ScriptedPoller([ButtonPresses(p1=True, p2=False)])
    dispatcher = _make_dispatcher(poller=poller, led_output=SimLedOutput(), calls=calls)

    player = dispatcher.run_once()

    assert player == 1
    assert calls == ["pong"]


def test_p2_press_launches_rhythm_jump() -> None:
    calls: list[str] = []
    poller = _ScriptedPoller([ButtonPresses(p1=False, p2=True)])
    dispatcher = _make_dispatcher(poller=poller, led_output=SimLedOutput(), calls=calls)

    player = dispatcher.run_once()

    assert player == 2
    assert calls == ["rhythm"]


def test_run_returns_to_idle_between_launches() -> None:
    calls: list[str] = []
    poller = _ScriptedPoller(
        [
            ButtonPresses(p1=True, p2=False),
            ButtonPresses(p1=False, p2=True),
        ],
    )
    dispatcher = _make_dispatcher(poller=poller, led_output=SimLedOutput(), calls=calls)

    dispatcher.run(max_launches=2)

    assert calls == ["pong", "rhythm"]


def test_idle_renders_breathing_markers() -> None:
    led_output = SimLedOutput()
    poller = _ScriptedPoller([ButtonPresses(p1=True, p2=False)])
    dispatcher = _make_dispatcher(poller=poller, led_output=led_output, calls=[])

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

    # Two markers of span 2 -> four lit pixels near each end.
    assert len(lit) == 4
    assert min(lit) < 5
    assert max(lit) > 14
