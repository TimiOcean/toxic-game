"""Tests for toxic_game.toml loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from toxic_game.config import clear_config_cache, load_app_config


@pytest.fixture(autouse=True)
def _clear_config_cache() -> None:
    clear_config_cache()


def test_load_default_config() -> None:
    config = load_app_config()

    assert config.gpio.left_contact_pin == 17
    assert config.gpio.right_contact_pin == 27
    assert config.gpio.debounce_ms == 30
    assert config.gpio.p1_input == "jumppad"
    assert config.gpio.p2_input == "button"
    assert config.gpio.jumppad.min_air_ms == 200
    assert config.gpio.jumppad.retrigger_ms == 400
    assert config.led.muted_rgb_count == 60
    assert config.led.rgbw_count == 30
    assert config.led.pin == 10
    assert config.led.data_interface == "spi"
    assert config.led.muted_rgbw_count == 45
    assert config.led.driver_count == 75
    assert config.led.total_count == 90
    assert config.led.active_count == 30
    assert config.led.rgbw_byte_order == "WRGB"
    assert config.led.hit_flash_ms == 500
    assert config.led.running_light_span == 2
    assert config.led.hit_marker_fraction == 0.10
    assert config.gameplay.lead_time_beats == 8
    assert config.gameplay.judgement_windows_ms.perfect == 100
    assert config.gameplay.judgement_windows_ms.good == 300
    assert config.gameplay.health.start == 20
    assert config.gameplay.health.max == 20
    assert config.gameplay.health.lose_on_error == 2
    assert config.gameplay.health.gain_on_good == 1
    assert config.gameplay.health.gain_on_perfect == 2
    assert config.runtime.update_hz == 60


def test_good_window_must_be_at_least_perfect(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.toml"
    config_path.write_text(
        """
[gameplay.judgement_windows_ms]
perfect = 50
good = 20
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="good judgement window"):
        load_app_config(config_path)


def test_rgbw_count_must_be_positive(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.toml"
    config_path.write_text(
        """
[led]
rgbw_count = 0
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="rgbw_count"):
        load_app_config(config_path)


def test_pong_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "empty.toml"
    config_path.write_text("", encoding="utf-8")

    config = load_app_config(config_path)

    assert config.pong.base_travel_ms == 1600
    assert config.pong.continuous_multiplier == 1.06
    assert config.pong.perfect_multiplier == 1.3
    assert config.pong.serve_delay_ms == 700
    assert config.pong.lives == 3
    assert config.pong.first_server == 1
    assert config.pong.auto_perfect_chance == 0.10
    assert config.pong.sfx.hit is None
    assert config.pong.sfx.perfect is None
    assert config.pong.sfx.miss is None
    assert config.pong.sfx.pitch_randomize == 0.05


def test_pong_sfx_paths_resolved_relative_to_config(tmp_path: Path) -> None:
    config_path = tmp_path / "cfg.toml"
    config_path.write_text(
        """
[pong.sfx]
hit = "sfx/hit.wav"
""",
        encoding="utf-8",
    )

    config = load_app_config(config_path)

    assert config.pong.sfx.hit == (tmp_path / "sfx" / "hit.wav").resolve()
    assert config.pong.sfx.perfect is None


def test_invalid_pong_first_server_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.toml"
    config_path.write_text(
        """
[pong]
first_server = 3
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="first_server"):
        load_app_config(config_path)


def test_invalid_input_type_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.toml"
    config_path.write_text(
        """
[gpio]
p1_input = "switch"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid p1_input"):
        load_app_config(config_path)
