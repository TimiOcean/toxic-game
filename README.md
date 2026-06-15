# Toxic Game

Cooperative two-player rhythm game for Raspberry Pi 3. Two buttons, one LED strip, audio playback.

## Setup

```bash
uv sync --group dev
uv sync --group pi    # pygame + rpi-ws281x (needed from Phase 1 onward)
```

## Config

All global numeric settings live in [`toxic_game.toml`](toxic_game.toml) (GPIO, LED, judgement windows, health, loop rate).

## Development

```bash
uv run pytest -q
```

## LED hardware check (Phase 1)

On the Pi (requires `uv sync --group pi` and usually `sudo` for GPIO DMA):

```bash
uv run tg-led --pattern solid --color magenta
uv run tg-led --pattern walk --color white
uv run tg-led --pattern dual-chase
uv run tg-led --pattern flash --side left --color white
uv run tg-led --pattern flash --side right --color red
```

Index 0 is the **left** end (Player 1). Patterns end by clearing the strip.

## Hardware reference

GPIO and LED patterns are adapted from the prototype at `/home/pi/rythm-jump`.
