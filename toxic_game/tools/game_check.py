"""Run a first end-to-end gameplay test for a song package."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from toxic_game.config import build_gameplay_config, build_led_config, build_runtime_config
from toxic_game.engine.button_manager import ButtonManager
from toxic_game.engine.game import GameManager
from toxic_game.engine.led_frames import CYAN, MAGENTA
from toxic_game.engine.notes import load_song_notes
from toxic_game.engine.score_animation import (
    build_full_flash_frame,
    build_tie_applause_frame,
    leds_to_light,
    run_applause_animation,
    run_score_animation,
)
from toxic_game.engine.song_config import load_song_by_id, resolve_song_dir
from toxic_game.engine.song_manager import SongManager
from toxic_game.hw.audio_playback import PygameAudioPlayer
from toxic_game.hw.led_output import NoOpLedOutput, Ws2811LedOutput
from toxic_game.hw.sfx import NoOpSfxPlayer, build_sfx_player

INTERRUPTED_EXIT_CODE = 130


def _write_dummy_taps(path: Path, *, bars: int, lane_offset: int) -> None:
    entries: list[str] = []
    for bar in range(1, bars + 1):
        beat = ((bar + lane_offset) % 4) + 1
        entries.append(f"{bar}.{beat}")
    path.write_text("\n".join(entries) + "\n", encoding="utf-8")


def ensure_dummy_taps(song_dir: Path, *, bars: int = 16) -> None:
    """Create simple tap files for first gameplay smoke tests."""
    _write_dummy_taps(song_dir / "p1.taps", bars=bars, lane_offset=0)
    _write_dummy_taps(song_dir / "p2.taps", bars=bars, lane_offset=2)


SEPARATED_LIGHTS_SPAWN = "center"


def run_game_check(
    *,
    song_id: str,
    duration_s: float | None,
    start_ms: int,
    make_dummy_taps: bool,
    sim_led: bool,
    solo_mode: bool,
    separated_lights: bool,
    mute: bool,
) -> int:
    """Run the integrated game loop using real audio, GPIO, and LEDs."""
    song = load_song_by_id(song_id)
    song_dir = resolve_song_dir(song_id)
    if make_dummy_taps:
        ensure_dummy_taps(song_dir)

    notes = load_song_notes(
        song_dir,
        song.timing,
        lead_time_beats=build_gameplay_config().lead_time_beats,
    )
    if not notes.player1 and not notes.player2:
        sys.stderr.write(
            "No tap files found. Add p1.taps/p2.taps or run with --dummy-taps.\n",
        )
        return 1

    use_sim_led = sim_led or os.geteuid() != 0
    if use_sim_led:
        led_output = NoOpLedOutput()
        if not sim_led:
            sys.stdout.write("Non-root run detected; using NoOp LED output.\n")
    else:
        led_output = Ws2811LedOutput()

    song_manager = SongManager(audio_player=PygameAudioPlayer())
    song_manager.load(song)
    gameplay_config = build_gameplay_config()
    led_config = build_led_config()
    if separated_lights:
        led_config = replace(
            led_config,
            running_light_spawn=SEPARATED_LIGHTS_SPAWN,  # type: ignore[arg-type]
        )
    sfx = NoOpSfxPlayer() if mute else build_sfx_player(gameplay_config.sfx)
    game = GameManager(
        song_manager=song_manager,
        button_manager=ButtonManager(),
        led_output=led_output,
        gameplay=gameplay_config,
        led=led_config,
        runtime=build_runtime_config(),
        solo_mode=solo_mode,
        sfx=sfx,
    )
    game.start(notes_p1=notes.player1, notes_p2=notes.player2, start_ms=start_ms)
    snapshot = game.run(max_duration_s=duration_s)

    p1_pct, p2_pct = game.final_percentages()
    sys.stdout.write(
        (
            "done "
            f"pos={snapshot.position_ms}ms "
            f"score_p1={snapshot.score_p1} "
            f"score_p2={snapshot.score_p2} "
            f"perfect={snapshot.perfect_count} "
            f"good={snapshot.good_count} "
            f"error={snapshot.error_count} "
            f"pending_p1={snapshot.pending_p1} "
            f"pending_p2={snapshot.pending_p2} "
            f"pct_p1={p1_pct}% "
            f"pct_p2={p2_pct}%\n"
        ),
    )

    half_len = led_config.active_count // 2
    run_score_animation(
        led_output=led_output,
        sfx=sfx,
        strip_len=led_config.active_count,
        p1_target=leds_to_light(p1_pct, half_len),
        p2_target=leds_to_light(p2_pct, half_len),
        step_ms=gameplay_config.score_step_ms,
    )
    if p1_pct > p2_pct:
        applause_frame = build_full_flash_frame(
            strip_len=led_config.active_count,
            color=MAGENTA,
        )
    elif p2_pct > p1_pct:
        applause_frame = build_full_flash_frame(
            strip_len=led_config.active_count,
            color=CYAN,
        )
    else:
        applause_frame = build_tie_applause_frame(strip_len=led_config.active_count)
    run_applause_animation(
        led_output=led_output,
        sfx=sfx,
        on_frame=applause_frame,
        count=gameplay_config.applause_flash_count,
        flash_ms=gameplay_config.applause_flash_ms,
    )
    song_manager.close()
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tg-game",
        description="Run integrated gameplay loop for a song package.",
    )
    parser.add_argument("song_id", help="Song folder name under songs/")
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Optional max runtime in seconds (default: until song ends).",
    )
    parser.add_argument(
        "--start-ms",
        type=int,
        default=0,
        help="Playback start offset in milliseconds.",
    )
    parser.add_argument(
        "--dummy-taps",
        action="store_true",
        help="Create simple p1/p2 dummy tap files before running.",
    )
    parser.add_argument(
        "--sim-led",
        action="store_true",
        help="Use in-memory LED output instead of physical strip (no root needed).",
    )
    parser.add_argument(
        "--solo",
        action="store_true",
        help="1-player debug: P2 errors do not reduce shared health.",
    )
    parser.add_argument(
        "--separated-lights",
        action="store_true",
        help=(
            "Spawn running lights at strip center and travel to side markers "
            "(magenta left, cyan right)."
        ),
    )
    parser.add_argument(
        "--mute",
        action="store_true",
        help="Disable the score-reveal chime sound effect.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the integrated game check CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return run_game_check(
            song_id=args.song_id,
            duration_s=args.duration,
            start_ms=args.start_ms,
            make_dummy_taps=args.dummy_taps,
            sim_led=args.sim_led,
            solo_mode=args.solo,
            separated_lights=args.separated_lights,
            mute=args.mute,
        )
    except KeyboardInterrupt:
        sys.stdout.write("Interrupted by user\n")
        return INTERRUPTED_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main())
