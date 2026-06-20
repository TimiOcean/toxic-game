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
    assert config.gpio.p2_input == "jumppad"
    assert config.gpio.jumppad.min_air_ms == 200
    assert config.gpio.jumppad.retrigger_ms == 400
    assert config.led.muted_rgb_count == 4
    assert config.led.rgbw_count == 70
    assert config.led.pin == 10
    assert config.led.data_interface == "spi"
    assert config.led.muted_rgbw_count == 3
    assert config.led.driver_count == 73
    assert config.led.total_count == 74
    assert config.led.active_count == 70
    assert config.led.rgbw_byte_order == "WRGB"
    assert config.led.hit_flash_ms == 500
    assert config.led.running_light_span == 4
    assert config.led.hit_marker_fraction == 0.10
    assert config.gameplay.lead_time_beats == 8
    assert config.gameplay.judgement_windows_ms.perfect == 200
    assert config.gameplay.judgement_windows_ms.good == 500
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
    assert config.pong.sfx.applause is None
    assert config.pong.sfx.chime is None
    assert config.pong.sfx.pitch_randomize == 0.05


def test_pong_distance_and_flash_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "empty.toml"
    config_path.write_text("", encoding="utf-8")

    config = load_app_config(config_path)

    assert config.pong.perfect_distance_leds == 1
    assert config.pong.good_distance_leds == 4
    assert config.pong.point_flash_count == 5
    assert config.pong.point_flash_intensity == 0.15
    assert config.pong.gameover_flash_count == 10
    assert config.pong.flash_ms == 150
    assert config.pong.score_step_ms == 750


def test_gameplay_score_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "empty.toml"
    config_path.write_text("", encoding="utf-8")

    config = load_app_config(config_path)

    assert config.gameplay.duration_s == 60
    assert config.gameplay.score_perfect == 3
    assert config.gameplay.score_good == 1
    assert config.gameplay.score_step_ms == 200
    assert config.gameplay.applause_flash_count == 10
    assert config.gameplay.applause_flash_ms == 150
    assert config.gameplay.empty_shutdown_s == 5
    assert config.gameplay.sfx.chime is None


def test_arcade_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "empty.toml"
    config_path.write_text("", encoding="utf-8")

    config = load_app_config(config_path)

    assert config.arcade.start_hold_ms == 500
    assert config.arcade.demo_idle_s == 600
    assert config.arcade.demo_volume == 0.30
    assert config.arcade.demo_miss_chance == 0.15


def test_invalid_arcade_demo_volume_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.toml"
    config_path.write_text(
        """
[arcade]
demo_volume = 1.5
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="demo_volume"):
        load_app_config(config_path)


def test_invalid_arcade_demo_miss_chance_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.toml"
    config_path.write_text(
        """
[arcade]
demo_miss_chance = -0.1
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="demo_miss_chance"):
        load_app_config(config_path)


def test_gameplay_sfx_path_resolved_relative_to_config(tmp_path: Path) -> None:
    config_path = tmp_path / "cfg.toml"
    config_path.write_text(
        """
[gameplay.sfx]
chime = "sfx/chime.wav"
""",
        encoding="utf-8",
    )

    config = load_app_config(config_path)

    assert config.gameplay.sfx.chime == (tmp_path / "sfx" / "chime.wav").resolve()


def test_gameplay_sfx_perfect_path_resolved_relative_to_config(tmp_path: Path) -> None:
    config_path = tmp_path / "cfg.toml"
    config_path.write_text(
        """
[gameplay.sfx]
perfect = "sfx/perfect_rythm.mp3"
""",
        encoding="utf-8",
    )

    config = load_app_config(config_path)

    assert config.gameplay.sfx.perfect == (
        tmp_path / "sfx" / "perfect_rythm.mp3"
    ).resolve()


def test_invalid_pong_distance_order_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.toml"
    config_path.write_text(
        """
[pong]
perfect_distance_leds = 5
good_distance_leds = 2
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="good_distance_leds"):
        load_app_config(config_path)


def test_led_running_light_spawn_default(tmp_path: Path) -> None:
    config_path = tmp_path / "empty.toml"
    config_path.write_text("", encoding="utf-8")

    config = load_app_config(config_path)

    assert config.led.running_light_spawn == "end"


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


def test_invalid_running_light_spawn_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.toml"
    config_path.write_text(
        """
[led]
running_light_spawn = "middle"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="running_light_spawn"):
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
