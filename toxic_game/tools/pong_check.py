"""Run the Pong game mode on real (or simulated) hardware."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

from toxic_game.config import (
    build_led_config,
    build_pong_config,
    build_runtime_config,
    load_app_config,
)
from toxic_game.engine.button_manager import ButtonManager
from toxic_game.engine.pong import PlayerId, PongManager
from toxic_game.hw.led_output import NoOpLedOutput, Ws2811LedOutput
from toxic_game.hw.sfx import NoOpSfxPlayer, build_sfx_player

INTERRUPTED_EXIT_CODE = 130


def run_pong_check(
    *,
    duration_s: float | None,
    sim_led: bool,
    solo_mode: bool,
    demo_mode: bool,
    mute: bool,
) -> int:
    """Run the integrated Pong loop using real GPIO, LEDs, and SFX."""
    app = load_app_config()
    pong_config = build_pong_config()

    auto_players: frozenset[PlayerId] = frozenset()
    if demo_mode:
        auto_players = frozenset({1, 2})
    elif solo_mode:
        auto_players = frozenset({2})

    use_sim_led = sim_led or os.geteuid() != 0
    if use_sim_led:
        led_output = NoOpLedOutput()
        if not sim_led:
            sys.stdout.write("Non-root run detected; using NoOp LED output.\n")
    else:
        led_output = Ws2811LedOutput()

    sfx = NoOpSfxPlayer() if mute else build_sfx_player(pong_config.sfx)

    game = PongManager(
        button_manager=ButtonManager(),
        led_output=led_output,
        led=build_led_config(),
        windows=app.gameplay.judgement_windows_ms,
        pong=pong_config,
        runtime=build_runtime_config(),
        sfx=sfx,
        auto_players=auto_players,
    )
    game.start()
    snapshot = game.run(max_duration_s=duration_s)

    sys.stdout.write(
        (
            "done "
            f"state={snapshot.state} "
            f"lives_p1={snapshot.lives_p1} "
            f"lives_p2={snapshot.lives_p2} "
            f"rallies={snapshot.rally_count} "
            f"perfect={snapshot.perfect_count} "
            f"good={snapshot.good_count} "
            f"miss={snapshot.miss_count} "
            f"game_over={snapshot.game_over}\n"
        ),
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tg-pong",
        description="Run the Pong game mode.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Optional max runtime in seconds (default: until game over).",
    )
    parser.add_argument(
        "--sim-led",
        action="store_true",
        help="Use in-memory LED output instead of physical strip (no root needed).",
    )
    parser.add_argument(
        "--solo",
        action="store_true",
        help="1-player: P2 is automated (always returns, 10%% perfect).",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Attract mode: both players automated.",
    )
    parser.add_argument(
        "--mute",
        action="store_true",
        help="Disable sound effects.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Pong CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return run_pong_check(
            duration_s=args.duration,
            sim_led=args.sim_led,
            solo_mode=args.solo,
            demo_mode=args.demo,
            mute=args.mute,
        )
    except KeyboardInterrupt:
        sys.stdout.write("Interrupted by user\n")
        return INTERRUPTED_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main())
