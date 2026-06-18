"""Run the always-on arcade dispatcher on real (or simulated) hardware."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

from toxic_game.config import (
    build_gameplay_config,
    build_led_config,
    build_pong_config,
    build_runtime_config,
)
from toxic_game.engine.arcade import ArcadeDispatcher
from toxic_game.engine.button_manager import ButtonManager
from toxic_game.engine.notes import load_song_notes
from toxic_game.engine.song_config import load_song_by_id, resolve_song_dir
from toxic_game.engine.song_manager import SongManager
from toxic_game.hw.audio_playback import PygameAudioPlayer
from toxic_game.hw.led_output import NoOpLedOutput, Ws2811LedOutput
from toxic_game.hw.sfx import NoOpSfxPlayer, build_sfx_player

INTERRUPTED_EXIT_CODE = 130


def run_arcade(*, song_id: str, sim_led: bool, mute: bool) -> int:
    """Run the idle dispatcher: P1 press -> Pong, P2 press -> rhythm jump."""
    gameplay = build_gameplay_config()
    led = build_led_config()
    pong = build_pong_config()
    runtime = build_runtime_config()

    song = load_song_by_id(song_id)
    song_dir = resolve_song_dir(song_id)
    notes = load_song_notes(song_dir, song.timing, lead_time_beats=gameplay.lead_time_beats)
    if not notes.player1 and not notes.player2:
        sys.stderr.write(
            f"No tap files found for song '{song_id}'. Add p1.taps/p2.taps.\n",
        )
        return 1

    use_sim_led = sim_led or os.geteuid() != 0
    if use_sim_led:
        led_output = NoOpLedOutput()
        if not sim_led:
            sys.stdout.write("Non-root run detected; using NoOp LED output.\n")
    else:
        led_output = Ws2811LedOutput()

    pong_sfx = NoOpSfxPlayer() if mute else build_sfx_player(pong.sfx)
    gameplay_sfx = NoOpSfxPlayer() if mute else build_sfx_player(gameplay.sfx)

    song_manager = SongManager(audio_player=PygameAudioPlayer())

    dispatcher = ArcadeDispatcher(
        button_manager=ButtonManager(),
        led_output=led_output,
        led=led,
        gameplay=gameplay,
        pong=pong,
        runtime=runtime,
        song=song,
        notes=notes,
        song_manager=song_manager,
        pong_sfx=pong_sfx,
        gameplay_sfx=gameplay_sfx,
    )

    sys.stdout.write(
        "Arcade ready: press Player 1 for Pong, Player 2 for Rhythm Jump.\n",
    )
    try:
        dispatcher.run()
    finally:
        song_manager.close()
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tg-arcade",
        description="Run the always-on arcade dispatcher.",
    )
    parser.add_argument(
        "--song",
        default="toxic",
        help="Song id for the rhythm jump mode (default: toxic).",
    )
    parser.add_argument(
        "--sim-led",
        action="store_true",
        help="Use in-memory LED output instead of physical strip (no root needed).",
    )
    parser.add_argument(
        "--mute",
        action="store_true",
        help="Disable all sound effects.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the arcade dispatcher CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return run_arcade(song_id=args.song, sim_led=args.sim_led, mute=args.mute)
    except KeyboardInterrupt:
        sys.stdout.write("Interrupted by user\n")
        return INTERRUPTED_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main())
