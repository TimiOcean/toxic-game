"""Song playback and musical timekeeping."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

from toxic_game.engine.song_config import SongConfig
from toxic_game.engine.timing import SongTiming, ms_to_absolute_beat, ms_to_bar_beat
from toxic_game.hw.audio_playback import AudioPlayer, NoOpAudioPlayer


class PlaybackClock(Protocol):
    """Protocol for monotonic clocks used by :class:`SongManager`."""

    def __call__(self) -> float:
        """Return the current time in seconds."""


class SongManager:
    """Play song audio and expose playback position in ms and beats."""

    def __init__(
        self,
        audio_player: AudioPlayer | None = None,
        *,
        clock: PlaybackClock | None = None,
    ) -> None:
        """Configure the manager with optional audio and clock dependencies."""
        self._audio_player = audio_player or NoOpAudioPlayer()
        self._clock = clock or time.monotonic
        self._song: SongConfig | None = None
        self._playing = False
        self._paused = False
        self._started_at_s: float | None = None
        self._paused_at_s: float | None = None
        self._paused_total_s = 0.0
        self._start_offset_ms = 0

    @property
    def song(self) -> SongConfig | None:
        """Return the loaded song, if any."""
        return self._song

    @property
    def timing(self) -> SongTiming | None:
        """Return timing parameters for the loaded song."""
        if self._song is None:
            return None
        return self._song.timing

    @property
    def is_playing(self) -> bool:
        """Return True while playback is active and not paused."""
        return self._playing and not self._paused

    def load(self, song: SongConfig) -> None:
        """Load a song without starting playback."""
        self.stop()
        self._song = song

    def play(self, *, start_ms: int = 0) -> None:
        """Start or restart playback for the loaded song."""
        if self._song is None:
            message = "cannot play before loading a song"
            raise RuntimeError(message)

        self._start_offset_ms = max(start_ms, 0)
        self._playing = True
        self._paused = False
        self._started_at_s = self._clock()
        self._paused_at_s = None
        self._paused_total_s = 0.0
        self._audio_player.play(self._song.audio_path, start_ms=self._start_offset_ms)

    def pause(self) -> None:
        """Pause playback while keeping the current position."""
        if not self._playing or self._paused:
            return
        self._paused = True
        self._paused_at_s = self._clock()
        self._audio_player.pause()

    def resume(self) -> None:
        """Resume playback after :meth:`pause`."""
        if not self._playing or not self._paused:
            return
        now = self._clock()
        if self._paused_at_s is not None:
            self._paused_total_s += now - self._paused_at_s
        self._paused_at_s = None
        self._paused = False
        self._audio_player.resume()

    def stop(self) -> None:
        """Stop playback and reset the transport position."""
        self._audio_player.stop()
        self._playing = False
        self._paused = False
        self._started_at_s = None
        self._paused_at_s = None
        self._paused_total_s = 0.0
        self._start_offset_ms = 0

    def close(self) -> None:
        """Release playback resources."""
        self.stop()
        self._audio_player.close()

    @property
    def position_ms(self) -> int:
        """Return the current playback position in milliseconds."""
        if not self._playing or self._started_at_s is None:
            return 0

        if self._paused and self._paused_at_s is not None:
            elapsed_s = self._paused_at_s - self._started_at_s - self._paused_total_s
        else:
            elapsed_s = self._clock() - self._started_at_s - self._paused_total_s

        return max(self._start_offset_ms + round(max(elapsed_s, 0.0) * 1000), 0)

    def current_absolute_beat(self) -> float | None:
        """Return the floating-point beat index at the current playback time."""
        timing = self.timing
        if timing is None:
            return None
        return ms_to_absolute_beat(timing, self.position_ms)

    def current_bar_beat(self) -> tuple[int, int] | None:
        """Return the current 1-based bar and beat, if on or after beat 0."""
        timing = self.timing
        if timing is None:
            return None
        return ms_to_bar_beat(timing, self.position_ms)

    def tick(self, *, now_s: float | None = None) -> int:
        """Advance a manual clock-based transport and return ``position_ms``.

        Useful in tests when no real-time sleep is desired.
        """
        if now_s is None:
            return self.position_ms
        if not self._playing or self._started_at_s is None or self._paused:
            return self.position_ms
        elapsed_s = max(now_s - self._started_at_s - self._paused_total_s, 0.0)
        return max(self._start_offset_ms + round(elapsed_s * 1000), 0)
