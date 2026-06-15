"""CLI for WS2811 LED strip hardware bring-up."""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

from toxic_game.config import build_led_config
from toxic_game.engine.led_frames import NAMED_COLORS, OFF, LedFrame, build_frame
from toxic_game.hw.led_output import Ws2811LedOutput
from toxic_game.hw.led_patterns import end_flash_pixels, pattern_frames, solid_pixels

DEFAULT_DELAY_S = 0.05
DEFAULT_REPEAT = 1
INTERRUPTED_EXIT_CODE = 130

PATTERN_CHOICES = (
    "solid",
    "walk",
    "p1-chase",
    "p2-chase",
    "dual-chase",
    "flash",
    "primaries",
)


class FrameWriter(Protocol):
    """Minimal interface required by the LED check command."""

    def write_frame(self, frame: LedFrame) -> None:
        """Render one LED frame."""


@dataclass(frozen=True, slots=True)
class LedCheckOptions:
    """Configuration for the LED hardware check."""

    pattern: str
    color_name: str
    side: str
    repeat: int
    delay_s: float


def _stdout_write(message: str) -> None:
    sys.stdout.write(message)


def run_led_check(
    *,
    options: LedCheckOptions,
    writer: FrameWriter | None = None,
    sleep: Callable[[float], None] = time.sleep,
    stdout: Callable[[str], None] = _stdout_write,
) -> None:
    """Drive the LED strip with a diagnostic pattern."""
    led_config = build_led_config()
    color = NAMED_COLORS[options.color_name]
    output: FrameWriter = writer or Ws2811LedOutput()
    stdout(
        "Driving RGBW output "
        f"(muted_rgb={led_config.muted_rgb_count}, "
        f"muted_rgbw={led_config.muted_rgbw_count}, "
        f"rgbw={led_config.rgbw_count}, "
        f"driver={led_config.driver_count}, pin={led_config.pin}, "
        f"pattern={options.pattern}, color={options.color_name})\n",
    )

    active = led_config.active_count
    if options.pattern == "flash":
        flash_color = NAMED_COLORS[options.color_name]
        side = "left" if options.side == "left" else "right"
        frames = [
            build_frame(
                end_flash_pixels(active, side, flash_color),
            ),
        ]
    else:
        frames = pattern_frames(
            pattern=options.pattern,
            count=active,
            span=led_config.running_light_span,
            color=color,
        )

    loops = options.repeat if options.repeat > 0 else 1
    for _ in range(loops):
        for frame in frames:
            output.write_frame(frame)
            sleep(options.delay_s)

    output.write_frame(build_frame(solid_pixels(active, OFF)))
    stdout("LED check finished; output cleared\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tg-led")
    parser.add_argument(
        "--pattern",
        choices=PATTERN_CHOICES,
        default="dual-chase",
        help="Diagnostic pattern to display.",
    )
    parser.add_argument(
        "--color",
        choices=tuple(NAMED_COLORS),
        default="magenta",
        help="Color for solid/walk/chase patterns.",
    )
    parser.add_argument(
        "--side",
        choices=("left", "right"),
        default="left",
        help="Strip end to flash (flash pattern only).",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=DEFAULT_REPEAT,
        help="How many times to run the pattern.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_S,
        help="Delay between frames in seconds.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the LED hardware check CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        run_led_check(
            options=LedCheckOptions(
                pattern=args.pattern,
                color_name=args.color,
                side=args.side,
                repeat=args.repeat,
                delay_s=args.delay,
            ),
        )
    except KeyboardInterrupt:
        sys.stdout.write("Interrupted by user\n")
        return INTERRUPTED_EXIT_CODE
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
