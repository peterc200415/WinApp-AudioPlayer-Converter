"""Audio playback and subtitle polling."""

from __future__ import annotations

import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

import pygame
from pydub import AudioSegment

from src.core.subtitle_parser import Subtitle, SubtitleParser
from src.utils.file_utils import get_auto_srt_file_path, get_srt_file_path, has_srt_file


def _ensure_ffmpeg_on_path() -> None:
    """Ensure FFmpeg is discoverable by pydub on Windows."""
    if os.name != "nt":
        return

    ffmpeg_bin = Path(r"C:\ffmpeg\bin")
    if not (ffmpeg_bin / "ffmpeg.exe").exists():
        return

    current_path = os.environ.get("PATH", "")
    if str(ffmpeg_bin) not in current_path:
        os.environ["PATH"] = f"{ffmpeg_bin};{current_path}" if current_path else str(ffmpeg_bin)


_ensure_ffmpeg_on_path()


class AudioPlayer:
    """Thin playback wrapper around pygame and pydub."""

    SUPPORTED_FORMATS = (
        ".mp3",
        ".m4a",
        ".wav",
        ".wma",
        ".flac",
        ".aac",
        ".ogg",
        ".opus",
        ".mp4",
    )
    DIRECT_PLAY_FORMATS = {".mp3", ".wav"}

    def __init__(self):
        pygame.mixer.init()
        self.current_file: Optional[str] = None
        self.playlist: List[str] = []
        self.current_index = -1
        self.current_duration = 0.0
        self.current_subtitles: List[Subtitle] = []
        self._subtitle_cache: Dict[str, List[Subtitle]] = {}

        self.is_playing = False
        self.is_paused = False
        self.is_closing = False
        self.volume = 1.0
        self.temp_files: List[str] = []

        self.on_position_changed: Optional[Callable[[float], None]] = None
        self.on_subtitle_changed: Optional[Callable[[Optional[Subtitle]], None]] = None
        self.on_playback_end: Optional[Callable[[], None]] = None
        self.on_subtitle_needed: Optional[Callable[[str], None]] = None

        self._subtitle_thread: Optional[threading.Thread] = None
        self._progress_thread: Optional[threading.Thread] = None
        self._last_subtitle_valid = False
        self._last_subtitle: Optional[Subtitle] = None

    def has_subtitles(self, audio_path: str) -> bool:
        if audio_path in self._subtitle_cache:
            return True
        return has_srt_file(audio_path)

    def set_cached_subtitles(self, audio_path: str, subtitles: List[Subtitle]) -> None:
        self._subtitle_cache[audio_path] = subtitles
        if self.current_file == audio_path:
            self.current_subtitles = subtitles
            self._last_subtitle_valid = False

    def load_file(self, file_path: str) -> bool:
        if not os.path.exists(file_path):
            print(f"Audio file not found: {file_path}")
            return False

        file_ext = Path(file_path).suffix.lower()
        if file_ext not in self.SUPPORTED_FORMATS:
            print(f"Unsupported audio format: {file_ext}")
            return False

        self.current_file = file_path
        self._load_subtitles(file_path)
        self._load_duration(file_path)
        return True

    def _load_subtitles(self, file_path: str) -> None:
        try:
            if file_path in self._subtitle_cache:
                self.current_subtitles = self._subtitle_cache[file_path]
                return

            srt_path = get_srt_file_path(file_path)
            if os.path.exists(srt_path):
                self.current_subtitles = SubtitleParser.parse_srt(srt_path)
                return

            auto_srt_path = get_auto_srt_file_path(file_path)
            if os.path.exists(auto_srt_path):
                self.current_subtitles = SubtitleParser.parse_srt(auto_srt_path)
                return

            self.current_subtitles = []
        except Exception as exc:
            print(f"Failed to load subtitles: {exc}")
            self.current_subtitles = []

    def _load_duration(self, file_path: str) -> None:
        try:
            audio = AudioSegment.from_file(file_path)
            self.current_duration = len(audio) / 1000.0
        except Exception as exc:
            print(f"Failed to read audio duration: {exc}")
            self.current_duration = 0.0

    def reload_subtitles(self, file_path: Optional[str] = None) -> bool:
        target = file_path or self.current_file
        if not target:
            return False

        srt_path = get_srt_file_path(target)
        try:
            if os.path.exists(srt_path):
                self.current_subtitles = SubtitleParser.parse_srt(srt_path)
                return True

            auto_srt_path = get_auto_srt_file_path(target)
            if os.path.exists(auto_srt_path):
                self.current_subtitles = SubtitleParser.parse_srt(auto_srt_path)
                return True

            self.current_subtitles = []
            return False
        except Exception as exc:
            print(f"Failed to reload subtitles: {exc}")
            self.current_subtitles = []
            return False

    def play(self, file_path: Optional[str] = None) -> bool:
        if file_path and not self.load_file(file_path):
            return False

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except Exception as exc:
            print(f"Failed to initialize audio device: {exc}")
            return False

        if not self.current_file:
            print("No audio file loaded.")
            return False

        self.stop()
        self._last_subtitle_valid = False

        file_ext = Path(self.current_file).suffix.lower()
        try:
            if file_ext in self.DIRECT_PLAY_FORMATS:
                pygame.mixer.music.load(self.current_file)
                pygame.mixer.music.set_volume(self.volume)
                pygame.mixer.music.play()
            elif file_ext in self.SUPPORTED_FORMATS:
                if not self._convert_and_play_with_pydub(file_ext):
                    return False
            else:
                print(f"Unsupported audio format: {file_ext}")
                return False

            self.is_playing = True
            self.is_paused = False
            self._start_subtitle_thread()
            self._start_progress_thread()

            if not self.current_subtitles and self.current_file and self.on_subtitle_needed:
                self.on_subtitle_needed(self.current_file)
            return True
        except Exception as exc:
            print(f"Playback failed: {exc}")
            return False

    def _convert_and_play_with_pydub(self, source_ext: str) -> bool:
        try:
            audio = AudioSegment.from_file(self.current_file)
            temp_wav_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_wav_file.close()
            audio.export(temp_wav_file.name, format="wav")
            self.temp_files.append(temp_wav_file.name)

            pygame.mixer.music.load(temp_wav_file.name)
            pygame.mixer.music.set_volume(self.volume)
            pygame.mixer.music.play()
            return True
        except Exception as exc:
            print(f"{source_ext} playback conversion failed: {exc}")
            return False

    def pause(self) -> None:
        if self.is_playing and not self.is_paused:
            pygame.mixer.music.pause()
            self.is_paused = True

    def unpause(self) -> None:
        if self.is_playing and self.is_paused:
            pygame.mixer.music.unpause()
            self.is_paused = False

    def toggle_pause(self) -> None:
        if self.is_paused:
            self.unpause()
        else:
            self.pause()

    def stop(self) -> None:
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass

        self.is_playing = False
        self.is_paused = False
        self._cleanup_temp_files()

    def get_position(self) -> float:
        if not self.is_playing:
            return 0.0
        pos = pygame.mixer.music.get_pos()
        return pos / 1000.0 if pos > 0 else 0.0

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(1.0, volume))
        pygame.mixer.music.set_volume(self.volume)

    def get_volume(self) -> float:
        return self.volume

    def set_playlist(self, file_list: List[str]) -> None:
        self.playlist = [path for path in file_list if Path(path).suffix.lower() in self.SUPPORTED_FORMATS]

    def next_track(self) -> bool:
        if not self.playlist:
            return False
        self.current_index = self.current_index + 1 if self.current_index < len(self.playlist) - 1 else 0
        return self.play(self.playlist[self.current_index])

    def previous_track(self) -> bool:
        if not self.playlist:
            return False
        self.current_index = self.current_index - 1 if self.current_index > 0 else len(self.playlist) - 1
        return self.play(self.playlist[self.current_index])

    def play_index(self, index: int) -> bool:
        if 0 <= index < len(self.playlist):
            self.current_index = index
            return self.play(self.playlist[index])
        return False

    def _start_subtitle_thread(self) -> None:
        if self._subtitle_thread and self._subtitle_thread.is_alive():
            return
        self._subtitle_thread = threading.Thread(target=self._update_subtitles, daemon=True)
        self._subtitle_thread.start()

    def _start_progress_thread(self) -> None:
        if self._progress_thread and self._progress_thread.is_alive():
            return
        self._progress_thread = threading.Thread(target=self._update_progress, daemon=True)
        self._progress_thread.start()

    def _update_subtitles(self) -> None:
        while self.is_playing and not self.is_closing:
            if not self.is_paused:
                current_time = self.get_position()
                subtitle = SubtitleParser.find_subtitle_by_time(self.current_subtitles, current_time)
                if self.on_subtitle_changed and (
                    (not self._last_subtitle_valid) or subtitle != self._last_subtitle
                ):
                    self._last_subtitle = subtitle
                    self._last_subtitle_valid = True
                    self.on_subtitle_changed(subtitle)
            time.sleep(0.5)

    def _update_progress(self) -> None:
        not_busy_ticks = 0
        loop_started_at = time.time()
        while self.is_playing and not self.is_closing:
            position = self.get_position()
            if not self.is_paused and self.on_position_changed:
                self.on_position_changed(position)

            if self.is_playing and not self.is_paused:
                is_busy = pygame.mixer.music.get_busy()
                if is_busy:
                    not_busy_ticks = 0
                else:
                    startup_grace = (time.time() - loop_started_at) <= 2.0
                    if startup_grace and position <= 0.2:
                        not_busy_ticks = 0
                    else:
                        not_busy_ticks += 1

                    reached_end = self.current_duration > 0 and position >= (self.current_duration - 0.3)
                    confirmed_end = not_busy_ticks >= 3
                    if reached_end or confirmed_end:
                        self.is_playing = False
                        if self.on_playback_end:
                            self.on_playback_end()
                        break

            time.sleep(0.25)

    def _cleanup_temp_files(self) -> None:
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    for _ in range(3):
                        try:
                            os.remove(temp_file)
                            break
                        except PermissionError:
                            time.sleep(0.1)
            except Exception as exc:
                print(f"Failed to clean temp file {temp_file}: {exc}")
        self.temp_files.clear()

    def cleanup(self) -> None:
        self.is_closing = True
        self.stop()
        self._cleanup_temp_files()
        pygame.mixer.quit()
