"""Admin CLI for creating song packages."""

from __future__ import annotations

import argparse
import shutil
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from toxic_game.config import build_path_config
from toxic_game.engine.song_config import load_song_config


@dataclass(frozen=True, slots=True)
class SongPackageOptions:
    """Inputs for creating a new song package."""

    song_id: str
    audio_source: Path
    name: str
    bpm: float
    delay_to_first_beat_ms: int


def _format_song_toml(
    *,
    name: str,
    audio_filename: str,
    bpm: float,
    delay_to_first_beat_ms: int,
) -> str:
    return "\n".join(
        [
            f'name = "{name}"',
            f'audio = "{audio_filename}"',
            f"bpm = {bpm}",
            f"delay_to_first_beat_ms = {delay_to_first_beat_ms}",
            "",
        ],
    )


def create_song_package(
    options: SongPackageOptions,
    *,
    songs_dir: Path | None = None,
) -> Path:
    """Create ``songs/<id>/`` with copied audio and ``song.toml``."""
    if options.bpm <= 0:
        message = "bpm must be > 0"
        raise ValueError(message)
    if options.delay_to_first_beat_ms < 0:
        message = "delay_to_first_beat_ms must be >= 0"
        raise ValueError(message)
    if not options.audio_source.exists():
        message = f"audio file not found: {options.audio_source}"
        raise FileNotFoundError(message)

    root = songs_dir or build_path_config().songs_dir
    song_dir = (root / options.song_id).resolve()
    song_dir.mkdir(parents=True, exist_ok=True)

    audio_filename = options.audio_source.name
    shutil.copy2(options.audio_source, song_dir / audio_filename)
    (song_dir / "song.toml").write_text(
        _format_song_toml(
            name=options.name,
            audio_filename=audio_filename,
            bpm=options.bpm,
            delay_to_first_beat_ms=options.delay_to_first_beat_ms,
        ),
        encoding="utf-8",
    )
    return song_dir


def run_song_config_tool(
    options: SongPackageOptions,
    *,
    songs_dir: Path | None = None,
) -> Path:
    """Create a song package and verify it loads."""
    song_dir = create_song_package(options, songs_dir=songs_dir)
    load_song_config(song_dir)
    return song_dir


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tg-song-config",
        description="Create a song package under songs/<id>/.",
    )
    parser.add_argument("song_id", help="Song folder name (e.g. toxic)")
    parser.add_argument("--audio", required=True, type=Path, help="Source audio file")
    parser.add_argument("--name", required=True, help="Display name for the song")
    parser.add_argument("--bpm", required=True, type=float, help="Beats per minute")
    parser.add_argument(
        "--delay-ms",
        type=int,
        default=0,
        help="Milliseconds from audio start to beat 0",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the song configuration CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        song_dir = run_song_config_tool(
            SongPackageOptions(
                song_id=args.song_id,
                audio_source=args.audio.expanduser().resolve(),
                name=args.name,
                bpm=args.bpm,
                delay_to_first_beat_ms=args.delay_ms,
            ),
        )
    except (FileNotFoundError, ValueError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    sys.stdout.write(f"created {song_dir}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
