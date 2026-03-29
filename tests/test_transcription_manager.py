from src.core.subtitle_parser import Subtitle
from src.core.transcription_manager import TranscriptionManager
from src.utils.config import Config


class DummyPlayer:
    def __init__(self):
        self.current_file = "track.wav"
        self.current_subtitles = []
        self.is_playing = False
        self.is_paused = False
        self._subtitle_cache = {}

    def get_position(self):
        return 0.0

    def set_cached_subtitles(self, path, subtitles):
        self._subtitle_cache[path] = subtitles
        if self.current_file == path:
            self.current_subtitles = subtitles


class DummyTranscriber:
    pass


def build_manager(tmp_path):
    config = Config(str(tmp_path / "settings.json"))
    manager = TranscriptionManager(DummyPlayer(), DummyTranscriber(), config, start_worker=False)
    return manager


def test_start_for_path_enqueues_first_preview_job(tmp_path):
    manager = build_manager(tmp_path)
    started = []
    manager.on_transcription_started = started.append

    manager.start_for_path("track.wav")

    job = manager._urgent_queue.get_nowait()
    assert job["path"] == "track.wav"
    assert job["start"] == 0
    assert job["model"] == "base"
    assert started == ["track.wav"]

    manager.shutdown()


def test_merge_subtitles_replaces_overlapping_upgrade_chunk(tmp_path):
    manager = build_manager(tmp_path)
    player = manager.player
    player._subtitle_cache["track.wav"] = [
        Subtitle(index=1, start_time=0.0, end_time=4.0, text="old 1"),
        Subtitle(index=2, start_time=5.0, end_time=9.0, text="old 2"),
        Subtitle(index=3, start_time=12.0, end_time=15.0, text="keep"),
    ]

    merged = manager._merge_subtitles(
        "track.wav",
        [Subtitle(index=1, start_time=5.0, end_time=10.0, text="new 2")],
        start_seconds=5,
        end_seconds=10,
        model="base",
    )

    assert [subtitle.text for subtitle in merged] == ["old 1", "new 2", "keep"]

    manager.shutdown()
