"""Sound-effect playback for short one-shot game cues.

Distinct from :mod:`toxic_game.hw.audio_playback`, which streams a single music
track. This plays short overlapping samples (hit / perfect / miss). Any effect
whose file is missing or fails to load is silently ignored.
"""

from __future__ import annotations

import importlib
import random
from array import array
from collections.abc import Callable, Sequence
from typing import Literal, Protocol

from toxic_game.config import SfxConfig
from toxic_game.hw.audio_device import ensure_pygame_mixer

SfxEvent = Literal["hit", "perfect", "miss", "applause", "chime"]


class SfxPlayer(Protocol):
    """Protocol for objects that play one-shot sound effects."""

    def play(self, event: SfxEvent) -> None:
        """Play the sample for ``event`` if one is available."""

    def set_volume(self, volume: float) -> None:
        """Set playback volume in ``[0.0, 1.0]``."""


class NoOpSfxPlayer:
    """Sound-effect player that ignores every request."""

    def play(self, event: SfxEvent) -> None:
        """Drop the request without playing anything."""
        _ = event

    def set_volume(self, volume: float) -> None:
        """Ignore volume changes."""
        _ = volume


class RecordingSfxPlayer:
    """In-memory sound-effect player that records requested events (tests)."""

    def __init__(self) -> None:
        """Track the ordered list of played events."""
        self.events: list[SfxEvent] = []
        self.volume = 1.0

    def play(self, event: SfxEvent) -> None:
        """Record the event instead of playing audio."""
        self.events.append(event)

    def set_volume(self, volume: float) -> None:
        """Store the requested volume for test assertions."""
        self.volume = max(0.0, min(1.0, volume))


def random_pitch_factor(
    pitch_randomize: float,
    rng: Callable[[], float] | None = None,
) -> float:
    """Return a playback pitch in ``[1 - pitch_randomize, 1 + pitch_randomize]``."""
    if pitch_randomize <= 0.0:
        return 1.0
    roll = (rng or random.random)()
    return 1.0 + pitch_randomize * (2.0 * roll - 1.0)


def _lerp_sample(a: int, b: int, frac: float) -> int:
    return int(a + (b - a) * frac)


def resample_mono_pitch(samples: Sequence[int], pitch: float) -> array:
    """Resample a mono sample buffer to change playback pitch."""
    if pitch <= 0.0:
        pitch = 1.0
    count = len(samples)
    if count == 0:
        return array("h")
    if abs(pitch - 1.0) < 1e-6:
        return array("h", samples)

    new_count = max(1, int(count / pitch))
    out = array("h", [0] * new_count)
    last_index = count - 1
    for index in range(new_count):
        position = index * pitch
        source_index = int(position)
        if source_index >= last_index:
            out[index] = int(samples[last_index])
            continue
        frac = position - source_index
        out[index] = _lerp_sample(
            int(samples[source_index]),
            int(samples[source_index + 1]),
            frac,
        )
    return out


def _resample_ndarray_pitch(samples: object, pitch: float) -> object:
    import numpy as np

    arr = np.asarray(samples)
    count = arr.shape[0]
    if count == 0:
        return arr
    new_count = max(1, int(count / pitch))
    positions = np.arange(new_count, dtype=np.float64) * pitch
    source_index = np.floor(positions).astype(np.int64)
    source_index = np.clip(source_index, 0, count - 2)
    frac = positions - source_index
    if arr.ndim == 1:
        a = arr[source_index]
        b = arr[source_index + 1]
        return (a + (b - a) * frac).astype(arr.dtype)
    a = arr[source_index, :]
    b = arr[source_index + 1, :]
    return (a + (b - a) * frac[:, None]).astype(arr.dtype)


def resample_pitch(samples: object, pitch: float) -> object:
    """Return ``samples`` resampled for the requested pitch factor."""
    ndim = getattr(samples, "ndim", None)
    if ndim in {1, 2}:
        return _resample_ndarray_pitch(samples, pitch)
    return resample_mono_pitch(samples, pitch)  # type: ignore[arg-type]


class PygameSfxPlayer:
    """Best-effort one-shot SFX player backed by ``pygame.mixer.Sound``."""

    def __init__(
        self,
        config: SfxConfig,
        *,
        rng: Callable[[], float] | None = None,
    ) -> None:
        """Load whatever sample files exist; missing ones stay silent."""
        self._pitch_randomize = config.pitch_randomize
        self._rng = rng or random.random
        self._volume = 1.0
        self._sounds: dict[SfxEvent, object] = {}
        self._pygame = None
        self._sndarray = None
        sound_factory = self._load_sound_factory()
        if sound_factory is None:
            return
        sources: dict[SfxEvent, object] = {
            "hit": config.hit,
            "perfect": config.perfect,
            "miss": config.miss,
            "applause": config.applause,
            "chime": config.chime,
        }
        for event, path in sources.items():
            if path is None:
                continue
            try:
                self._sounds[event] = sound_factory(str(path))
            except Exception:  # noqa: BLE001 - any load failure -> silent effect
                continue

    def _load_sound_factory(self):
        try:
            pygame = importlib.import_module("pygame")
        except ImportError:
            return None
        mixer = ensure_pygame_mixer()
        if mixer is None:
            return None
        self._pygame = pygame
        self._sndarray = getattr(pygame, "sndarray", None)
        return getattr(mixer, "Sound", None)

    def set_volume(self, volume: float) -> None:
        """Set playback volume in ``[0.0, 1.0]``."""
        self._volume = max(0.0, min(1.0, volume))

    def _play_with_pitch(self, sound: object, pitch: float) -> None:
        if abs(pitch - 1.0) < 1e-6 or self._sndarray is None:
            sound.set_volume(self._volume)  # type: ignore[attr-defined]
            sound.play()  # type: ignore[attr-defined]
            return
        try:
            shifted = resample_pitch(self._sndarray.array(sound), pitch)
            pitched = self._sndarray.make_sound(shifted)
            pitched.set_volume(self._volume)  # type: ignore[attr-defined]
            pitched.play()
        except Exception:  # noqa: BLE001
            sound.set_volume(self._volume)  # type: ignore[attr-defined]
            sound.play()  # type: ignore[attr-defined]

    def play(self, event: SfxEvent) -> None:
        """Play the loaded sample for ``event`` if present."""
        sound = self._sounds.get(event)
        if sound is None:
            return
        try:
            pitch = random_pitch_factor(self._pitch_randomize, self._rng)
            self._play_with_pitch(sound, pitch)
        except Exception:  # noqa: BLE001
            return


def build_sfx_player(config: SfxConfig) -> SfxPlayer:
    """Return a pygame-backed player, falling back to no-op when unavailable."""
    return PygameSfxPlayer(config)
