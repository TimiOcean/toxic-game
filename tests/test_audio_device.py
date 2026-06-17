"""Tests for ALSA headphone device discovery."""

from __future__ import annotations

from toxic_game.hw.audio_device import _device_from_cards_text, find_headphone_alsa_device


def test_device_from_cards_text_prefers_headphones_card() -> None:
  cards = "\n".join(
      [
          " 0 [Headphones     ]: bcm2835_headpho - bcm2835 Headphones",
          " 1 [vc4hdmi        ]: vc4-hdmi - vc4-hdmi",
      ],
  )

  assert _device_from_cards_text(cards) == "plughw:0,0"


def test_device_from_cards_text_when_hdmi_is_card_zero() -> None:
  cards = "\n".join(
      [
          " 0 [vc4hdmi        ]: vc4-hdmi - vc4-hdmi",
          " 1 [Headphones     ]: bcm2835_headpho - bcm2835 Headphones",
      ],
  )

  assert _device_from_cards_text(cards) == "plughw:1,0"


def test_ensure_pygame_mixer_uses_pi_friendly_settings(monkeypatch) -> None:
    init_args: dict[str, object] = {}
    initialized = False

    class FakeSound:
        def __init__(self, *, buffer: bytes) -> None:
            self.buffer = buffer

        def play(self) -> None:
            return None

    class FakeMixer:
        def get_init(self) -> object | None:
            return object() if initialized else None

        def init(
            self,
            *,
            frequency: int,
            size: int,
            channels: int,
            buffer: int,
        ) -> None:
            nonlocal initialized
            initialized = True
            init_args.update(
                frequency=frequency,
                size=size,
                channels=channels,
                buffer=buffer,
            )

        Sound = FakeSound

    monkeypatch.setattr(
        "toxic_game.hw.audio_device.importlib.import_module",
        lambda name: type("Pygame", (), {"mixer": FakeMixer()})(),
    )

    from toxic_game.hw.audio_device import ensure_pygame_mixer

    mixer = ensure_pygame_mixer()

    assert mixer is not None
    assert init_args == {
        "frequency": 44100,
        "size": -16,
        "channels": 2,
        "buffer": 2048,
    }


def test_find_headphone_alsa_device_on_pi(monkeypatch) -> None:
  monkeypatch.setattr(
      "toxic_game.hw.audio_device.Path.exists",
      lambda self: True,
  )
  monkeypatch.setattr(
      "toxic_game.hw.audio_device.Path.read_text",
      lambda self, encoding="utf-8": (
          " 0 [Headphones     ]: bcm2835_headpho - bcm2835 Headphones\n"
      ),
  )

  assert find_headphone_alsa_device() == "plughw:0,0"
