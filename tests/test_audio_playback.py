"""Tests for audio playback adapters."""

from __future__ import annotations

from pathlib import Path

from toxic_game.hw.audio_playback import NoOpAudioPlayer, PygameAudioPlayer


def test_noop_audio_player_accepts_calls(tmp_path: Path) -> None:
    player = NoOpAudioPlayer()
    audio_path = tmp_path / "track.ogg"
    audio_path.write_bytes(b"fake")

    assert player.is_active() is False
    player.play(audio_path, start_ms=100)
    assert player.is_active() is True
    player.pause()
    player.resume()
    player.stop()
    assert player.is_active() is False
    player.close()


def test_pygame_audio_player_without_pygame(tmp_path: Path, monkeypatch) -> None:
    audio_path = tmp_path / "track.ogg"
    audio_path.write_bytes(b"fake")

    class FakeMusic:
        def load(self, filename: str) -> None:
            _ = filename

        def play(self, *, start: float = 0.0) -> None:
            _ = start

        def pause(self) -> None:
            return None

        def unpause(self) -> None:
            return None

        def stop(self) -> None:
            return None

        def get_busy(self) -> bool:
            return False

    class FakeMixer:
        music = FakeMusic()

        def get_init(self) -> object:
            return object()

        def init(self) -> None:
            return None

        def quit(self) -> None:
            return None

    monkeypatch.setattr(
        "toxic_game.hw.audio_playback.PygameAudioPlayer._load_mixer",
        lambda self: FakeMixer(),
    )
    player = PygameAudioPlayer()

    player.play(audio_path)
    assert player.is_active() is False
    player.pause()
    assert player.is_active() is True
    player.resume()
    player.stop()
    player.close()
