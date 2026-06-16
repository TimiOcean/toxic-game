"""Tests for song playback and musical timekeeping."""

from __future__ import annotations

from pathlib import Path

import pytest

from toxic_game.engine.song_config import SongConfig
from toxic_game.engine.song_manager import SongManager
from toxic_game.hw.audio_playback import NoOpAudioPlayer


class FakeClock:
    """Mutable monotonic clock for transport tests."""

    def __init__(self, start_s: float = 0.0) -> None:
        self.now_s = start_s

    def __call__(self) -> float:
        return self.now_s


class RecordingAudioPlayer(NoOpAudioPlayer):
    """Capture audio player calls for assertions."""

    def __init__(self) -> None:
        super().__init__()
        self.play_calls: list[tuple[Path, int]] = []
        self.pause_count = 0
        self.resume_count = 0
        self.stop_count = 0

    def play(self, audio_path: Path, *, start_ms: int = 0) -> None:
        super().play(audio_path, start_ms=start_ms)
        self.play_calls.append((audio_path, start_ms))

    def pause(self) -> None:
        super().pause()
        self.pause_count += 1

    def resume(self) -> None:
        super().resume()
        self.resume_count += 1

    def stop(self) -> None:
        super().stop()
        self.stop_count += 1


class ControllableAudioPlayer(NoOpAudioPlayer):
    """Audio player with an overridable active state for transport tests."""

    def __init__(self) -> None:
        super().__init__()
        self.force_active: bool | None = None

    def is_active(self) -> bool:
        if self.force_active is not None:
            return self.force_active
        return super().is_active()


@pytest.fixture
def demo_song(tmp_path: Path) -> SongConfig:
    audio_path = tmp_path / "track.ogg"
    audio_path.write_bytes(b"fake")
    return SongConfig(
        song_id="demo",
        name="Demo",
        audio_path=audio_path,
        bpm=120.0,
        delay_to_first_beat_ms=500,
    )


def test_play_advances_position_ms(demo_song: SongConfig) -> None:
    clock = FakeClock()
    audio = RecordingAudioPlayer()
    manager = SongManager(audio_player=audio, clock=clock)
    manager.load(demo_song)

    manager.play()
    clock.now_s = 1.5

    assert manager.position_ms == 1500
    assert manager.is_playing is True
    assert audio.play_calls == [(demo_song.audio_path, 0)]


def test_pause_freezes_position(demo_song: SongConfig) -> None:
    clock = FakeClock()
    manager = SongManager(audio_player=RecordingAudioPlayer(), clock=clock)
    manager.load(demo_song)
    manager.play()

    clock.now_s = 1.0
    manager.pause()
    clock.now_s = 4.0

    assert manager.position_ms == 1000
    assert manager.is_playing is False


def test_resume_continues_from_pause(demo_song: SongConfig) -> None:
    clock = FakeClock()
    manager = SongManager(audio_player=RecordingAudioPlayer(), clock=clock)
    manager.load(demo_song)
    manager.play()

    clock.now_s = 1.0
    manager.pause()
    clock.now_s = 3.0
    manager.resume()
    clock.now_s = 4.0

    assert manager.position_ms == 2000


def test_current_bar_beat(demo_song: SongConfig) -> None:
    clock = FakeClock()
    manager = SongManager(audio_player=NoOpAudioPlayer(), clock=clock)
    manager.load(demo_song)
    manager.play()

    clock.now_s = 5.0
    assert manager.current_absolute_beat() == 9.0
    assert manager.current_bar_beat() == (3, 2)


def test_play_requires_loaded_song() -> None:
    manager = SongManager(audio_player=NoOpAudioPlayer())
    with pytest.raises(RuntimeError):
        manager.play()


def test_stop_resets_position(demo_song: SongConfig) -> None:
    clock = FakeClock()
    manager = SongManager(audio_player=RecordingAudioPlayer(), clock=clock)
    manager.load(demo_song)
    manager.play()
    clock.now_s = 2.0
    manager.stop()

    assert manager.position_ms == 0
    assert manager.is_playing is False


def test_is_playing_false_when_audio_finishes(demo_song: SongConfig) -> None:
    clock = FakeClock()
    audio = ControllableAudioPlayer()
    manager = SongManager(audio_player=audio, clock=clock)
    manager.load(demo_song)
    manager.play()

    clock.now_s = 2.5
    audio.force_active = False

    assert manager.is_playing is False
    assert manager.position_ms == 2500
