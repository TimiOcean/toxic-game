"""CLI for song audio playback and timing verification."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass

from toxic_game.engine.song_config import load_song_by_id
from toxic_game.engine.song_manager import SongManager
from toxic_game.engine.timing import format_bar_beat
from toxic_game.hw.audio_playback import PygameAudioPlayer

DEFAULT_INTERVAL_S = 0.25
INTERRUPTED_EXIT_CODE = 130


@dataclass(frozen=True, slots=True)
class AudioCheckOptions:
    """Configuration for the audio timing check."""

    song_id: str
    duration_s: float
    interval_s: float
    start_ms: int


def run_audio_check(options: AudioCheckOptions) -> None:
    """Play a song and print playback position with bar.beat markers."""
    song = load_song_by_id(options.song_id)
    manager = SongManager(audio_player=PygameAudioPlayer())
    manager.load(song)
    manager.play(start_ms=options.start_ms)

    deadline = time.monotonic() + options.duration_s
    try:
        while time.monotonic() < deadline and manager.is_playing:
            bar_beat = manager.current_bar_beat()
            bar_text = (
                format_bar_beat(*bar_beat)
                if bar_beat is not None
                else "pre-roll"
            )
            beat = manager.current_absolute_beat()
            beat_text = f"{beat:.2f}" if beat is not None else "n/a"
            sys.stdout.write(
                f"pos={manager.position_ms:5d}ms  beat={beat_text:>6}  bar.beat={bar_text}\n",
            )
            sys.stdout.flush()
            time.sleep(options.interval_s)
    finally:
        manager.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Play a song and print playback timing markers.",
    )
    parser.add_argument("song_id", help="Song folder name under songs/")
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="How long to run before stopping (seconds).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL_S,
        help="Delay between timing prints (seconds).",
    )
    parser.add_argument(
        "--start-ms",
        type=int,
        default=0,
        help="Playback start offset in milliseconds.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the audio timing check CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        run_audio_check(
            options=AudioCheckOptions(
                song_id=args.song_id,
                duration_s=args.duration,
                interval_s=args.interval,
                start_ms=args.start_ms,
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
