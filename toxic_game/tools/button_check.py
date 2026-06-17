"""CLI for GPIO button hardware bring-up."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from toxic_game.config import build_gpio_config
from toxic_game.engine.button_manager import (
    ButtonManager,
    ButtonPresses,
    CallableButtonReader,
    SimButtonReader,
)
from toxic_game.hw.gpio_input import ButtonSide, gpio_is_available, read_button_states

DEFAULT_INTERVAL_S = 0.01
INTERRUPTED_EXIT_CODE = 130


class ButtonPoller(Protocol):
    """Minimal interface required by the button check command."""

    def poll(self) -> ButtonPresses:
        """Detect presses since the previous poll."""


@dataclass(frozen=True, slots=True)
class ButtonCheckOptions:
    """Configuration for the button hardware check."""

    samples: int
    interval_s: float
    show_held: bool


def _stdout_write(message: str) -> None:
    sys.stdout.write(message)


def _format_held_states(states: dict[ButtonSide, bool]) -> str:
    left = "ON" if states["left"] else "off"
    right = "ON" if states["right"] else "off"
    return f"held left={left} right={right}"


def run_button_check(
    *,
    options: ButtonCheckOptions,
    manager: ButtonPoller | None = None,
    reader: SimButtonReader | CallableButtonReader | None = None,
    sleep: Callable[[float], None] = time.sleep,
    stdout: Callable[[str], None] = _stdout_write,
) -> None:
    """Poll buttons and print edge-triggered press events."""
    gpio_config = build_gpio_config()
    state_reader = reader or CallableButtonReader(read_button_states)
    poller = manager or ButtonManager(reader=state_reader)
    stdout(
        "Polling player inputs "
        f"(P1 pin={gpio_config.left_contact_pin} {gpio_config.p1_input}, "
        f"P2 pin={gpio_config.right_contact_pin} {gpio_config.p2_input}, "
        f"debounce_ms={gpio_config.debounce_ms}, "
        f"jumppad min_air_ms={gpio_config.jumppad.min_air_ms}, "
        f"retrigger_ms={gpio_config.jumppad.retrigger_ms})\n",
    )
    if not gpio_is_available():
        stdout(
            "WARNING: RPi.GPIO is not available in this Python environment. "
            "Install python3-rpi.gpio or recreate the venv with "
            "--system-site-packages.\n",
        )

    previous_held: dict[ButtonSide, bool] | None = None
    remaining = options.samples
    while True:
        held = state_reader.read_states()
        if options.show_held and held != previous_held:
            stdout(f"{_format_held_states(held)}\n")
            previous_held = dict(held)

        presses = poller.poll()
        if presses.p1:
            stdout("P1 pressed\n")
        if presses.p2:
            stdout("P2 pressed\n")

        if remaining > 0:
            remaining -= 1
            if remaining == 0:
                break
        sleep(options.interval_s)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tg-button")
    parser.add_argument(
        "--samples",
        type=int,
        default=0,
        help="Number of poll iterations (0 = run until interrupted).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL_S,
        help="Delay between polls in seconds.",
    )
    parser.add_argument(
        "--show-held",
        action="store_true",
        help="Also print when a button is held down or released.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the button hardware check CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        run_button_check(
            options=ButtonCheckOptions(
                samples=args.samples,
                interval_s=args.interval,
                show_held=args.show_held,
            ),
        )
    except KeyboardInterrupt:
        sys.stdout.write("Interrupted by user\n")
        return INTERRUPTED_EXIT_CODE
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
