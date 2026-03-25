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
    assert config.led.count == 60
    assert config.led.hit_flash_ms == 180
    assert config.led.running_light_span == 4
    assert config.gameplay.lead_time_beats == 4
    assert config.gameplay.judgement_windows_ms.perfect == 20
    assert config.gameplay.judgement_windows_ms.good == 50
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
