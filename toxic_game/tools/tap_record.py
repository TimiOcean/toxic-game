"""Live tap recording CLI for authoring per-player tap note files."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from toxic_game.config import build_runtime_config
from toxic_game.engine.button_manager import ButtonManager
from toxic_game.engine.song_config import load_song_by_id, resolve_song_dir
from toxic_game.engine.song_manager import SongManager
from toxic_game.engine.tap_quantize import (
    RecordedTap,
    quantize_recorded_taps,
    write_tap_files,
)
from toxic_game.engine.timing import format_bar_beat, ms_to_bar_beat
from toxic_game.hw.audio_playback import PygameAudioPlayer

INTERRUPTED_EXIT_CODE = 130


@dataclass
class TapRecorder:
    """Capture raw button presses while a song plays."""

    song_manager: SongManager
    button_manager: ButtonManager
    recordings: list[RecordedTap] = field(default_factory=list)

    def poll_once(self) -> None:
        """Record any presses that occurred since the last poll."""
        now_ms = self.song_manager.position_ms
        presses = self.button_manager.poll()
        if presses.p1:
            self.recordings.append(RecordedTap(player=1, press_ms=now_ms))
        if presses.p2:
            self.recordings.append(RecordedTap(player=2, press_ms=now_ms))

    def run(self, *, max_duration_s: float | None = None) -> list[RecordedTap]:
        """Play the loaded song and capture taps until stop or timeout."""
        tick_s = 1.0 / max(build_runtime_config().update_hz, 1)
        deadline = (
            time.monotonic() + max_duration_s
            if max_duration_s is not None
            else None
        )
        self.poll_once()
        while self.song_manager.is_playing:
            if deadline is not None and time.monotonic() >= deadline:
                self.song_manager.stop()
                break
            time.sleep(tick_s)
            self.poll_once()
        return list(self.recordings)


@dataclass(frozen=True, slots=True)
class TapRecordOptions:
    """Configuration for a tap recording session."""

    song_id: str
    duration_s: float | None


def run_tap_record(options: TapRecordOptions) -> tuple[Path, Path]:
    """Record taps for a song and write ``p1.taps`` / ``p2.taps``."""
    song = load_song_by_id(options.song_id)
    song_dir = resolve_song_dir(options.song_id)
    song_manager = SongManager(audio_player=PygameAudioPlayer())
    song_manager.load(song)
    song_manager.play()

    recorder = TapRecorder(
        song_manager=song_manager,
        button_manager=ButtonManager(),
    )
    try:
        recordings = recorder.run(max_duration_s=options.duration_s)
    finally:
        song_manager.close()

    p1_lines, p2_lines = quantize_recorded_taps(song.timing, tuple(recordings))
    paths = write_tap_files(song_dir, p1_lines=p1_lines, p2_lines=p2_lines)

    for tap in recordings:
        bar_beat = ms_to_bar_beat(song.timing, tap.press_ms)
        bar_text = (
            format_bar_beat(*bar_beat)
            if bar_beat is not None
            else "pre-roll"
        )
        sys.stdout.write(
            f"P{tap.player} raw={tap.press_ms:5d}ms  quantized={bar_text}\n",
        )
    sys.stdout.write(
        f"wrote {paths[0]} ({len(p1_lines)} taps), "
        f"{paths[1]} ({len(p2_lines)} taps)\n",
    )
    return paths


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tg-tap-record",
        description="Record p1/p2 tap files for a song while audio plays.",
    )
    parser.add_argument("song_id", help="Song folder name under songs/")
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Optional max recording time in seconds (default: full song).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the tap recording CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        run_tap_record(
            TapRecordOptions(
                song_id=args.song_id,
                duration_s=args.duration,
            ),
        )
    except KeyboardInterrupt:
        sys.stdout.write("Interrupted by user\n")
        return INTERRUPTED_EXIT_CODE
    except FileNotFoundError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
