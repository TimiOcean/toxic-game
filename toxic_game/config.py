"""Central configuration helpers for paths, hardware, and gameplay."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal

InputType = Literal["button", "jumppad"]
_VALID_INPUT_TYPES = frozenset({"button", "jumppad"})
RunningLightSpawn = Literal["end", "center"]
_VALID_RUNNING_LIGHT_SPAWN = frozenset({"end", "center"})


def repo_root_dir() -> Path:
    """Return the repository root directory."""
    return Path(__file__).resolve().parents[1]


DEFAULT_CONFIG_PATH = repo_root_dir() / "toxic_game.toml"


@dataclass(frozen=True, slots=True)
class PathConfig:
    """Filesystem locations used by the application."""

    repo_root: Path
    songs_dir: Path


@dataclass(frozen=True, slots=True)
class JumppadConfig:
    """Timing rules for jumppad landing detection."""

    min_air_ms: int
    retrigger_ms: int


@dataclass(frozen=True, slots=True)
class GpioConfig:
    """GPIO input pin assignments and per-player input mode."""

    left_contact_pin: int
    right_contact_pin: int
    debounce_ms: int
    p1_input: InputType
    p2_input: InputType
    jumppad: JumppadConfig


@dataclass(frozen=True, slots=True)
class LedConfig:
    """LED strip configuration for the physical output adapter."""

    muted_rgb_count: int
    rgbw_count: int
    pin: int
    freq_hz: int
    dma: int
    invert: bool
    brightness: int
    channel: int
    hit_flash_ms: int
    running_light_span: int
    rgbw_byte_order: str
    hit_marker_fraction: float
    running_light_spawn: RunningLightSpawn

    @property
    def total_count(self) -> int:
        """Physical LEDs on the data line (muted RGB + active RGBW)."""
        return self.muted_rgb_count + self.rgbw_count

    @property
    def active_count(self) -> int:
        """Gameplay LEDs (RGBW segment only)."""
        return self.rgbw_count

    @property
    def muted_rgbw_count(self) -> int:
        """Black RGBW driver pixels clocking through the leading RGB segment."""
        if self.muted_rgb_count == 0:
            return 0
        rgb_bytes = self.muted_rgb_count * 3
        return (rgb_bytes + 3) // 4

    @property
    def driver_count(self) -> int:
        """Uniform RGBW pixels passed to rpi_ws281x."""
        return self.muted_rgbw_count + self.rgbw_count

    @property
    def data_interface(self) -> str:
        """Return ``spi`` or ``pwm`` based on the configured data GPIO pin."""
        return "spi" if self.pin == 10 else "pwm"


@dataclass(frozen=True, slots=True)
class JudgementWindowsMs:
    """Timing windows for perfect and good hits."""

    perfect: int
    good: int


@dataclass(frozen=True, slots=True)
class HealthConfig:
    """Shared cooperative health pool settings."""

    start: int
    max: int
    lose_on_error: int
    gain_on_good: int
    gain_on_perfect: int


@dataclass(frozen=True, slots=True)
class GameplayConfig:
    """Gameplay tuning loaded from config."""

    lead_time_beats: int
    judgement_windows_ms: JudgementWindowsMs
    health: HealthConfig
    duration_s: int
    score_perfect: int
    score_good: int
    score_step_ms: int
    empty_shutdown_s: int
    sfx: SfxConfig


@dataclass(frozen=True, slots=True)
class ArcadeConfig:
    """Arcade dispatcher tuning."""

    start_hold_ms: int


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Runtime loop settings."""

    update_hz: int


@dataclass(frozen=True, slots=True)
class SfxConfig:
    """Optional sound-effect file paths. ``None`` means the effect is silent."""

    hit: Path | None
    perfect: Path | None
    miss: Path | None
    applause: Path | None
    chime: Path | None
    pitch_randomize: float


@dataclass(frozen=True, slots=True)
class PongConfig:
    """Tuning for the Pong game mode."""

    base_travel_ms: int
    continuous_multiplier: float
    perfect_multiplier: float
    serve_delay_ms: int
    lives: int
    first_server: int
    auto_perfect_chance: float
    perfect_distance_leds: int
    good_distance_leds: int
    point_flash_count: int
    point_flash_intensity: float
    gameover_flash_count: int
    flash_ms: int
    sfx: SfxConfig


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Top-level application configuration."""

    paths: PathConfig
    gpio: GpioConfig
    led: LedConfig
    gameplay: GameplayConfig
    runtime: RuntimeConfig
    pong: PongConfig
    arcade: ArcadeConfig


def _resolve_config_path(path: str | Path | None) -> Path:
    if path is None:
        return DEFAULT_CONFIG_PATH
    return Path(path).expanduser().resolve()


def _read_toml_table(document: dict[str, object], key: str) -> dict[str, object]:
    value = document.get(key, {})
    if not isinstance(value, dict):
        message = f"{key} must be a TOML table"
        raise TypeError(message)
    return value


def _read_int(table: dict[str, object], key: str, default: int) -> int:
    value = table.get(key, default)
    if type(value) is int:
        return value
    return default


def _read_float(table: dict[str, object], key: str, default: float) -> float:
    value = table.get(key, default)
    if type(value) in {int, float}:
        return float(value)
    return default


def _read_bool(table: dict[str, object], key: str, *, default: bool) -> bool:
    value = table.get(key, default)
    if type(value) is bool:
        return value
    return default


def _read_str(table: dict[str, object], key: str, default: str) -> str:
    value = table.get(key, default)
    if type(value) is str:
        return value
    return default


def _read_path(
    config_dir: Path,
    table: dict[str, object],
    key: str,
    default: str,
) -> Path:
    raw_value = table.get(key, default)
    if not isinstance(raw_value, str):
        raw_value = default
    candidate = Path(raw_value).expanduser()
    if candidate.is_absolute():
        return candidate
    return (config_dir / candidate).resolve()


def _read_optional_path(
    config_dir: Path,
    table: dict[str, object],
    key: str,
) -> Path | None:
    raw_value = table.get(key)
    if not isinstance(raw_value, str) or not raw_value.strip():
        return None
    candidate = Path(raw_value).expanduser()
    if candidate.is_absolute():
        return candidate
    return (config_dir / candidate).resolve()


def _build_judgement_windows(table: dict[str, object]) -> JudgementWindowsMs:
    windows_table = _read_toml_table(table, "judgement_windows_ms")
    perfect = _read_int(windows_table, "perfect", 20)
    good = _read_int(windows_table, "good", 50)
    if good < perfect:
        message = "good judgement window must be >= perfect window"
        raise ValueError(message)
    return JudgementWindowsMs(perfect=perfect, good=good)


def _build_sfx_config(config_dir: Path, table: dict[str, object]) -> SfxConfig:
    pitch_randomize = _read_float(table, "pitch_randomize", 0.05)
    if not 0.0 <= pitch_randomize <= 1.0:
        message = "sfx pitch_randomize must be between 0 and 1"
        raise ValueError(message)
    return SfxConfig(
        hit=_read_optional_path(config_dir, table, "hit"),
        perfect=_read_optional_path(config_dir, table, "perfect"),
        miss=_read_optional_path(config_dir, table, "miss"),
        applause=_read_optional_path(config_dir, table, "applause"),
        chime=_read_optional_path(config_dir, table, "chime"),
        pitch_randomize=pitch_randomize,
    )


def _build_health(table: dict[str, object]) -> HealthConfig:
    health_table = _read_toml_table(table, "health")
    return HealthConfig(
        start=_read_int(health_table, "start", 20),
        max=_read_int(health_table, "max", 20),
        lose_on_error=_read_int(health_table, "lose_on_error", 2),
        gain_on_good=_read_int(health_table, "gain_on_good", 1),
        gain_on_perfect=_read_int(health_table, "gain_on_perfect", 2),
    )


def _build_jumppad_config(table: dict[str, object]) -> JumppadConfig:
    jumppad_table = _read_toml_table(table, "jumppad")
    min_air_ms = _read_int(jumppad_table, "min_air_ms", 200)
    retrigger_ms = _read_int(jumppad_table, "retrigger_ms", 400)
    if min_air_ms < 0:
        message = "jumppad min_air_ms must be >= 0"
        raise ValueError(message)
    if retrigger_ms < 0:
        message = "jumppad retrigger_ms must be >= 0"
        raise ValueError(message)
    return JumppadConfig(min_air_ms=min_air_ms, retrigger_ms=retrigger_ms)


def _build_gpio_config(gpio_table: dict[str, object]) -> GpioConfig:
    p1_input = _read_str(gpio_table, "p1_input", "button")
    p2_input = _read_str(gpio_table, "p2_input", "button")
    for name, value in (("p1_input", p1_input), ("p2_input", p2_input)):
        if value not in _VALID_INPUT_TYPES:
            message = f"invalid {name}: {value!r} (expected button or jumppad)"
            raise ValueError(message)
    return GpioConfig(
        left_contact_pin=_read_int(gpio_table, "left_contact_pin", 17),
        right_contact_pin=_read_int(gpio_table, "right_contact_pin", 27),
        debounce_ms=_read_int(gpio_table, "debounce_ms", 30),
        p1_input=p1_input,  # type: ignore[arg-type]
        p2_input=p2_input,  # type: ignore[arg-type]
        jumppad=_build_jumppad_config(gpio_table),
    )


def _build_led_config(led_table: dict[str, object]) -> LedConfig:
    muted_rgb_count = _read_int(led_table, "muted_rgb_count", 0)
    legacy_count = led_table.get("count")
    if "rgbw_count" in led_table:
        rgbw_count = _read_int(led_table, "rgbw_count", 60)
    elif type(legacy_count) is int:
        rgbw_count = legacy_count
    else:
        rgbw_count = 60

    if muted_rgb_count < 0:
        message = "muted_rgb_count must be >= 0"
        raise ValueError(message)
    if rgbw_count < 1:
        message = "rgbw_count must be >= 1"
        raise ValueError(message)

    running_light_spawn = _read_str(led_table, "running_light_spawn", "end")
    if running_light_spawn not in _VALID_RUNNING_LIGHT_SPAWN:
        message = f"invalid running_light_spawn: {running_light_spawn!r} (expected end or center)"
        raise ValueError(message)

    return LedConfig(
        muted_rgb_count=muted_rgb_count,
        rgbw_count=rgbw_count,
        pin=_read_int(led_table, "pin", 18),
        freq_hz=_read_int(led_table, "freq_hz", 800000),
        dma=_read_int(led_table, "dma", 10),
        invert=_read_bool(led_table, "invert", default=False),
        brightness=_read_int(led_table, "brightness", 255),
        channel=_read_int(led_table, "channel", 0),
        hit_flash_ms=_read_int(led_table, "hit_flash_ms", 180),
        running_light_span=_read_int(led_table, "running_light_span", 4),
        rgbw_byte_order=_read_str(led_table, "rgbw_byte_order", "WRGB"),
        hit_marker_fraction=_read_float(led_table, "hit_marker_fraction", 0.10),
        running_light_spawn=running_light_spawn,  # type: ignore[arg-type]
    )


def _build_arcade_config(table: dict[str, object]) -> ArcadeConfig:
    start_hold_ms = _read_int(table, "start_hold_ms", 500)
    if start_hold_ms < 1:
        message = "arcade start_hold_ms must be >= 1"
        raise ValueError(message)
    return ArcadeConfig(start_hold_ms=start_hold_ms)


def _build_pong_config(
    config_dir: Path,
    pong_table: dict[str, object],
) -> PongConfig:
    base_travel_ms = _read_int(pong_table, "base_travel_ms", 1600)
    continuous_multiplier = _read_float(pong_table, "continuous_multiplier", 1.06)
    perfect_multiplier = _read_float(pong_table, "perfect_multiplier", 1.3)
    serve_delay_ms = _read_int(pong_table, "serve_delay_ms", 700)
    lives = _read_int(pong_table, "lives", 3)
    first_server = _read_int(pong_table, "first_server", 1)
    auto_perfect_chance = _read_float(pong_table, "auto_perfect_chance", 0.10)
    perfect_distance_leds = _read_int(pong_table, "perfect_distance_leds", 1)
    good_distance_leds = _read_int(pong_table, "good_distance_leds", 4)
    point_flash_count = _read_int(pong_table, "point_flash_count", 5)
    point_flash_intensity = _read_float(pong_table, "point_flash_intensity", 0.15)
    gameover_flash_count = _read_int(pong_table, "gameover_flash_count", 10)
    flash_ms = _read_int(pong_table, "flash_ms", 150)

    if base_travel_ms < 1:
        message = "pong base_travel_ms must be >= 1"
        raise ValueError(message)
    if continuous_multiplier <= 0 or perfect_multiplier <= 0:
        message = "pong multipliers must be > 0"
        raise ValueError(message)
    if serve_delay_ms < 0:
        message = "pong serve_delay_ms must be >= 0"
        raise ValueError(message)
    if lives < 1:
        message = "pong lives must be >= 1"
        raise ValueError(message)
    if first_server not in {1, 2}:
        message = "pong first_server must be 1 or 2"
        raise ValueError(message)
    if not 0.0 <= auto_perfect_chance <= 1.0:
        message = "pong auto_perfect_chance must be between 0 and 1"
        raise ValueError(message)
    if perfect_distance_leds < 0 or good_distance_leds < 0:
        message = "pong distance windows must be >= 0"
        raise ValueError(message)
    if good_distance_leds < perfect_distance_leds:
        message = "pong good_distance_leds must be >= perfect_distance_leds"
        raise ValueError(message)
    if point_flash_count < 0 or gameover_flash_count < 0:
        message = "pong flash counts must be >= 0"
        raise ValueError(message)
    if not 0.0 <= point_flash_intensity <= 1.0:
        message = "pong point_flash_intensity must be between 0 and 1"
        raise ValueError(message)
    if flash_ms < 1:
        message = "pong flash_ms must be >= 1"
        raise ValueError(message)

    sfx = _build_sfx_config(config_dir, _read_toml_table(pong_table, "sfx"))

    return PongConfig(
        base_travel_ms=base_travel_ms,
        continuous_multiplier=continuous_multiplier,
        perfect_multiplier=perfect_multiplier,
        serve_delay_ms=serve_delay_ms,
        lives=lives,
        first_server=first_server,
        auto_perfect_chance=auto_perfect_chance,
        perfect_distance_leds=perfect_distance_leds,
        good_distance_leds=good_distance_leds,
        point_flash_count=point_flash_count,
        point_flash_intensity=point_flash_intensity,
        gameover_flash_count=gameover_flash_count,
        flash_ms=flash_ms,
        sfx=sfx,
    )


@cache
def _load_app_config_cached(config_path: Path) -> AppConfig:
    config_dir = config_path.parent
    if config_path.exists():
        document = tomllib.loads(config_path.read_text(encoding="utf-8"))
    else:
        document = {}

    paths_table = _read_toml_table(document, "paths")
    gpio_table = _read_toml_table(document, "gpio")
    led_table = _read_toml_table(document, "led")
    gameplay_table = _read_toml_table(document, "gameplay")
    runtime_table = _read_toml_table(document, "runtime")
    pong_table = _read_toml_table(document, "pong")
    arcade_table = _read_toml_table(document, "arcade")

    empty_shutdown_s = _read_int(gameplay_table, "empty_shutdown_s", 5)
    if empty_shutdown_s < 1:
        message = "gameplay empty_shutdown_s must be >= 1"
        raise ValueError(message)

    return AppConfig(
        paths=PathConfig(
            repo_root=repo_root_dir(),
            songs_dir=_read_path(config_dir, paths_table, "songs_dir", "songs"),
        ),
        gpio=_build_gpio_config(gpio_table),
        led=_build_led_config(led_table),
        gameplay=GameplayConfig(
            lead_time_beats=_read_int(gameplay_table, "lead_time_beats", 4),
            judgement_windows_ms=_build_judgement_windows(gameplay_table),
            health=_build_health(gameplay_table),
            duration_s=_read_int(gameplay_table, "duration_s", 60),
            score_perfect=_read_int(gameplay_table, "score_perfect", 3),
            score_good=_read_int(gameplay_table, "score_good", 1),
            score_step_ms=_read_int(gameplay_table, "score_step_ms", 200),
            empty_shutdown_s=empty_shutdown_s,
            sfx=_build_sfx_config(config_dir, _read_toml_table(gameplay_table, "sfx")),
        ),
        runtime=RuntimeConfig(
            update_hz=_read_int(runtime_table, "update_hz", 60),
        ),
        pong=_build_pong_config(config_dir, pong_table),
        arcade=_build_arcade_config(arcade_table),
    )


def clear_config_cache() -> None:
    """Clear cached config values so tests can swap configuration files."""
    _load_app_config_cached.cache_clear()


def load_app_config(path: str | Path | None = None) -> AppConfig:
    """Load the complete application configuration from TOML."""
    return _load_app_config_cached(_resolve_config_path(path))


def build_path_config(path: str | Path | None = None) -> PathConfig:
    """Return filesystem path configuration."""
    return load_app_config(path).paths


def build_gpio_config(path: str | Path | None = None) -> GpioConfig:
    """Return GPIO pin assignments for the two players."""
    return load_app_config(path).gpio


def build_led_config(path: str | Path | None = None) -> LedConfig:
    """Return WS281x strip configuration."""
    return load_app_config(path).led


def build_gameplay_config(path: str | Path | None = None) -> GameplayConfig:
    """Return gameplay tuning configuration."""
    return load_app_config(path).gameplay


def build_runtime_config(path: str | Path | None = None) -> RuntimeConfig:
    """Return runtime loop configuration."""
    return load_app_config(path).runtime


def build_pong_config(path: str | Path | None = None) -> PongConfig:
    """Return Pong game-mode configuration."""
    return load_app_config(path).pong


def build_arcade_config(path: str | Path | None = None) -> ArcadeConfig:
    """Return arcade dispatcher configuration."""
    return load_app_config(path).arcade
