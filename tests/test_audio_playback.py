"""Tests for audio playback adapters."""

from __future__ import annotations

from pathlib import Path

from toxic_game.hw.audio_playback import NoOpAudioPlayer, PygameAudioPlayer


def test_noop_audio_player_accepts_calls(tmp_path: Path) -> None:
    player = NoOpAudioPlayer()
    audio_path = tmp_path / "track.ogg"
    audio_path.write_bytes(b"fake")

    player.play(audio_path, start_ms=100)
    player.pause()
    player.resume()
    player.stop()
    player.close()


def test_pygame_audio_player_without_pygame(tmp_path: Path) -> None:
    player = PygameAudioPlayer()
    audio_path = tmp_path / "track.ogg"
    audio_path.write_bytes(b"fake")

    player.play(audio_path)
    player.pause()
    player.resume()
    player.stop()
    player.close()
