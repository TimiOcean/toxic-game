"""Tests for live tap recording CLI."""

from __future__ import annotations

from pathlib import Path

from toxic_game.config import GpioConfig, JumppadConfig
from toxic_game.engine.button_manager import ButtonManager, SimButtonReader
from toxic_game.engine.notes import load_tap_file
from toxic_game.engine.song_config import SongConfig
from toxic_game.engine.song_manager import SongManager
from toxic_game.engine.tap_quantize import RecordedTap
from toxic_game.hw.audio_playback import NoOpAudioPlayer
from toxic_game.tools.tap_record import TapRecorder, TapRecordOptions, run_tap_record


def _song_config(tmp_path: Path) -> SongConfig:
    audio_path = tmp_path / "audio.ogg"
    audio_path.write_bytes(b"fake")
    return SongConfig(
        song_id="demo",
        name="Demo",
        audio_path=audio_path,
        bpm=120.0,
        delay_to_first_beat_ms=500,
    )


def test_tap_recorder_captures_rising_edges() -> None:
    clock_s = [0.0]
    song = SongConfig(
        song_id="demo",
        name="Demo",
        audio_path=Path("audio.ogg"),
        bpm=120.0,
        delay_to_first_beat_ms=0,
    )
    song_manager = SongManager(NoOpAudioPlayer(), clock=lambda: clock_s[0])
    song_manager.load(song)
    song_manager.play(start_ms=1000)

    reader = SimButtonReader({"left": False, "right": False})
    buttons = ButtonManager(
        reader=reader,
        gpio_config=GpioConfig(
            left_contact_pin=17,
            right_contact_pin=27,
            debounce_ms=30,
            p1_input="button",
            p2_input="button",
            jumppad=JumppadConfig(min_air_ms=200, retrigger_ms=400),
        ),
        debounce_ms=0,
        clock_ms=lambda: int(clock_s[0] * 1000),
    )
    recorder = TapRecorder(song_manager=song_manager, button_manager=buttons)

    reader.states["left"] = True
    recorder.poll_once()
    reader.states["left"] = False
    recorder.poll_once()

    assert recorder.recordings == [RecordedTap(player=1, press_ms=1000)]


def test_run_tap_record_writes_quantized_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    songs_dir = tmp_path / "songs"
    song_dir = songs_dir / "demo"
    song_dir.mkdir(parents=True)
    (song_dir / "audio.ogg").write_bytes(b"fake")
    (song_dir / "song.toml").write_text(
        "\n".join(
            [
                'name = "Demo"',
                'audio = "audio.ogg"',
                "bpm = 120.0",
                "delay_to_first_beat_ms = 500",
                "",
            ],
        ),
        encoding="utf-8",
    )

    def fake_run(
        self: TapRecorder,
        *,
        max_duration_s: float | None = None,
    ) -> list[RecordedTap]:
        _ = max_duration_s
        return [
            RecordedTap(player=1, press_ms=1000),
            RecordedTap(player=2, press_ms=1500),
        ]

    monkeypatch.setattr(TapRecorder, "run", fake_run)
    monkeypatch.setattr(
        "toxic_game.tools.tap_record.PygameAudioPlayer",
        NoOpAudioPlayer,
    )
    monkeypatch.setattr(
        "toxic_game.tools.tap_record.resolve_song_dir",
        lambda song_id, songs_dir=None: song_dir,
    )
    monkeypatch.setattr(
        "toxic_game.tools.tap_record.load_song_by_id",
        lambda song_id, songs_dir=None: _song_config(song_dir),
    )

    p1_path, p2_path = run_tap_record(
        TapRecordOptions(song_id="demo", duration_s=None),
    )

    assert p1_path == song_dir / "p1.taps"
    assert p2_path == song_dir / "p2.taps"
    assert load_tap_file(p1_path) == [(1, 2)]
    assert load_tap_file(p2_path) == [(1, 3)]
