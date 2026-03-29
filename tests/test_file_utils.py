from pathlib import Path

from src.utils.file_utils import find_audio_files, get_auto_srt_file_path, has_srt_file


def test_find_audio_files_searches_subdirectories(tmp_path):
    root_track = tmp_path / "root.mp3"
    nested_dir = tmp_path / "Album"
    nested_dir.mkdir()
    nested_track = nested_dir / "nested.wav"
    ignored_file = nested_dir / "notes.txt"

    root_track.write_text("x", encoding="utf-8")
    nested_track.write_text("x", encoding="utf-8")
    ignored_file.write_text("x", encoding="utf-8")

    files = find_audio_files(str(tmp_path), extensions=[".mp3", ".wav"])

    assert str(root_track) in files
    assert str(nested_track) in files
    assert str(ignored_file) not in files


def test_has_srt_file_accepts_auto_srt_sidecar(tmp_path):
    audio = tmp_path / "song.mp3"
    audio.write_text("x", encoding="utf-8")
    auto_srt = tmp_path / Path(get_auto_srt_file_path(str(audio))).name
    auto_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")

    assert has_srt_file(str(audio)) is True
