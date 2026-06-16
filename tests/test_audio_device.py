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
