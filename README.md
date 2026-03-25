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
uv run ruff check .
uv run ruff format .
```

## Hardware reference

GPIO and LED patterns are adapted from the prototype at `/home/pi/rythm-jump`.
