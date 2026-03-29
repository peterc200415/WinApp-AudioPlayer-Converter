"""Background transcription orchestration for the Qt UI."""

from __future__ import annotations

import queue
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Callable, Optional

from src.core.audio_player import AudioPlayer
from src.core.subtitle_parser import Subtitle
from src.core.transcriber import Transcriber
from src.utils.config import Config
from src.utils.file_utils import get_auto_srt_file_path
from src.utils.time_utils import format_time


class TranscriptionManager:
    """Schedules chunk-based transcription work for the active track."""

    def __init__(
        self,
        player: AudioPlayer,
        transcriber: Transcriber,
        config: Config,
        start_worker: bool = True,
    ) -> None:
        self.player = player
        self.transcriber = transcriber
        self.config = config

        self.on_transcription_started: Optional[Callable[[str], None]] = None
        self.on_transcription_ready: Optional[Callable[[str, str], None]] = None
        self.on_transcription_failed: Optional[Callable[[str, str, str], None]] = None

        self._lock = threading.Lock()
        self._current_generation = 0
        self._transcribing_paths: set[str] = set()
        self._inflight: set[tuple[str, int, str, int]] = set()
        self._preview_next_start: dict[str, int] = {}
        self._upgrade_next_start: dict[str, int] = {}

        self._urgent_queue: "queue.Queue[Optional[dict]]" = queue.Queue()
        self._bg_queue: "queue.Queue[Optional[dict]]" = queue.Queue()
        self._worker_stop = threading.Event()
        self._worker = threading.Thread(target=self._transcription_worker, daemon=True)
        if start_worker:
            self._worker.start()

    def start_for_path(self, audio_path: str) -> None:
        """Begin subtitle generation for the active audio path."""
        if not self.config.get("auto_transcribe_on_play", True):
            return
        if self.player.current_file != audio_path:
            return

        with self._lock:
            first_start = audio_path not in self._transcribing_paths
            self._transcribing_paths.add(audio_path)
            self._preview_next_start.setdefault(audio_path, 0)
            self._upgrade_next_start.setdefault(audio_path, 0)
            generation = self._current_generation

        if first_start and self.on_transcription_started:
            self.on_transcription_started(audio_path)

        self._enqueue_chunk_job(
            path=audio_path,
            start_seconds=0,
            seconds=int(self.config.get("subtitle_preview_seconds", 20)),
            model=self._preview_model_name(),
            generation=generation,
            urgent=True,
        )

    def cancel_active(self) -> None:
        """Invalidate queued/running jobs for the current generation."""
        with self._lock:
            self._current_generation += 1
            self._transcribing_paths.clear()
            self._inflight.clear()
            self._preview_next_start.clear()
            self._upgrade_next_start.clear()

        self._drain_queue(self._urgent_queue)
        self._drain_queue(self._bg_queue)

    def tick(self) -> None:
        """Schedule additional transcription work while playback is active."""
        if not self.player.is_playing or self.player.is_paused:
            return

        path = self.player.current_file
        if not path:
            return

        with self._lock:
            if path not in self._transcribing_paths:
                return
            generation = self._current_generation
            preview_next = int(self._preview_next_start.get(path, 0))
            upgrade_next = int(self._upgrade_next_start.get(path, 0))

        position = self.player.get_position()
        lead_seconds = int(self.config.get("subtitle_chunk_lead_seconds", 12))
        preview_chunk = int(self.config.get("subtitle_preview_seconds", 20))
        upgrade_chunk = int(self.config.get("base_chunk_seconds", 45))
        upgrade_start = int(self.config.get("upgrade_start_after_seconds", 60))

        if int(position + lead_seconds) >= preview_next:
            self._enqueue_chunk_job(
                path=path,
                start_seconds=preview_next,
                seconds=preview_chunk,
                model=self._preview_model_name(),
                generation=generation,
                urgent=True,
            )
            with self._lock:
                self._preview_next_start[path] = preview_next + preview_chunk

        if not self.config.get("enable_full_transcription", True):
            return

        preview_covered = self._get_cached_coverage(path)
        if preview_covered < upgrade_start:
            return

        if int(position + lead_seconds) >= upgrade_next and (upgrade_next + upgrade_chunk) <= int(preview_covered + 1):
            self._enqueue_chunk_job(
                path=path,
                start_seconds=upgrade_next,
                seconds=upgrade_chunk,
                model=self._upgrade_model_name(),
                generation=generation,
                urgent=False,
            )
            with self._lock:
                self._upgrade_next_start[path] = upgrade_next + upgrade_chunk

    def is_transcribing(self, path: str) -> bool:
        with self._lock:
            if path not in self._transcribing_paths:
                return False
            return any(inflight_path == path for inflight_path, _start, _model, _gen in self._inflight)

    def shutdown(self) -> None:
        self._worker_stop.set()
        try:
            self._urgent_queue.put_nowait(None)
        except Exception:
            pass
        try:
            self._bg_queue.put_nowait(None)
        except Exception:
            pass
        if self._worker.is_alive():
            self._worker.join(timeout=2.0)

    @staticmethod
    def _drain_queue(q: "queue.Queue[Optional[dict]]") -> None:
        while True:
            try:
                q.get_nowait()
                q.task_done()
            except Exception:
                break

    def _preview_model_name(self) -> str:
        return str(self.config.get("subtitle_preview_model", "base"))

    def _upgrade_model_name(self) -> str:
        return str(self.config.get("whisper_model", "base"))

    def _enqueue_chunk_job(
        self,
        path: str,
        start_seconds: int,
        seconds: int,
        model: str,
        generation: int,
        urgent: bool,
    ) -> None:
        if seconds <= 0:
            return

        key = (path, int(start_seconds), model, int(generation))
        with self._lock:
            if key in self._inflight:
                return
            self._inflight.add(key)

        job = {
            "path": path,
            "start": int(start_seconds),
            "seconds": int(seconds),
            "model": model,
            "generation": int(generation),
        }
        if urgent:
            self._urgent_queue.put(job)
        else:
            self._bg_queue.put(job)

    def _transcription_worker(self) -> None:
        while not self._worker_stop.is_set():
            job = self._dequeue_job()
            if job is None:
                continue

            path = str(job.get("path", ""))
            start_seconds = int(job.get("start", 0))
            seconds = int(job.get("seconds", 0))
            model = str(job.get("model", self._preview_model_name()))
            generation = int(job.get("generation", -1))

            if not path or seconds <= 0:
                self._mark_inflight_done(path, start_seconds, model, generation)
                continue

            if self._is_stale_job(path, generation):
                self._mark_inflight_done(path, start_seconds, model, generation)
                continue

            preview_wav = self._make_preview_wav(path, start_seconds, seconds)
            if not preview_wav:
                self._mark_inflight_done(path, start_seconds, model, generation)
                continue

            try:
                kwargs = {
                    "beam_size": self.config.get("whisper_beam_size", 1),
                    "best_of": self.config.get("whisper_best_of", 1),
                }
                language = self.config.get("whisper_language", "auto")
                if language and language != "auto":
                    kwargs["language"] = language

                result_subs = self.transcriber.transcribe_to_subtitles(
                    preview_wav,
                    model_name=model,
                    device=self.config.get("device", "auto"),
                    **kwargs,
                )
            except Exception as exc:
                if self.on_transcription_failed:
                    self.on_transcription_failed(path, model, str(exc))
                self._mark_inflight_done(path, start_seconds, model, generation)
                try:
                    Path(preview_wav).unlink(missing_ok=True)
                except Exception:
                    pass
                continue

            try:
                Path(preview_wav).unlink(missing_ok=True)
            except Exception:
                pass

            if self._is_stale_job(path, generation):
                self._mark_inflight_done(path, start_seconds, model, generation)
                continue

            offset_subs = self._offset_subtitles(result_subs, float(start_seconds))
            if offset_subs:
                merged = self._merge_subtitles(path, offset_subs, start_seconds, start_seconds + seconds, model)
                self.player.set_cached_subtitles(path, merged)
                self._write_auto_srt(path, merged)

            if self.on_transcription_ready:
                self.on_transcription_ready(path, model)
            self._mark_inflight_done(path, start_seconds, model, generation)

    def _dequeue_job(self) -> Optional[dict]:
        try:
            return self._urgent_queue.get(timeout=0.2)
        except queue.Empty:
            pass

        try:
            return self._bg_queue.get(timeout=0.2)
        except queue.Empty:
            return None

    def _is_stale_job(self, path: str, generation: int) -> bool:
        with self._lock:
            if generation != self._current_generation:
                return True
        return self.player.current_file != path

    def _mark_inflight_done(self, path: str, start_seconds: int, model: str, generation: int) -> None:
        with self._lock:
            self._inflight.discard((path, int(start_seconds), model, int(generation)))

    def _make_preview_wav(self, audio_path: str, start_seconds: int, seconds: int) -> Optional[str]:
        if seconds <= 0:
            return None

        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp_path = tmp.name
            tmp.close()

            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                str(max(0, int(start_seconds))),
                "-t",
                str(seconds),
                "-i",
                audio_path,
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "wav",
                tmp_path,
            ]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            if proc.returncode != 0:
                Path(tmp_path).unlink(missing_ok=True)
                return None
            return tmp_path
        except Exception:
            return None

    @staticmethod
    def _offset_subtitles(subtitles: list[Subtitle], offset: float) -> list[Subtitle]:
        out: list[Subtitle] = []
        for i, subtitle in enumerate(subtitles, start=1):
            text = subtitle.text.strip()
            if not text:
                continue
            out.append(
                Subtitle(
                    index=i,
                    start_time=subtitle.start_time + offset,
                    end_time=subtitle.end_time + offset,
                    text=text,
                )
            )
        return out

    def _merge_subtitles(
        self,
        path: str,
        new_subs: list[Subtitle],
        start_seconds: int,
        end_seconds: int,
        model: str,
    ) -> list[Subtitle]:
        current = []
        cache = getattr(self.player, "_subtitle_cache", {})
        if path in cache:
            current = list(cache[path])
        elif self.player.current_file == path:
            current = list(self.player.current_subtitles)

        if model == self._upgrade_model_name():
            kept = [subtitle for subtitle in current if subtitle.end_time < start_seconds or subtitle.start_time > end_seconds]
            merged = kept + new_subs
        else:
            merged = current + new_subs

        merged.sort(key=lambda subtitle: (subtitle.start_time, subtitle.end_time))
        dedup: list[Subtitle] = []
        last_key = None
        for subtitle in merged:
            key = (round(subtitle.start_time, 3), round(subtitle.end_time, 3), subtitle.text)
            if key == last_key:
                continue
            dedup.append(subtitle)
            last_key = key
        return dedup

    def _get_cached_coverage(self, path: str) -> float:
        cache = getattr(self.player, "_subtitle_cache", {})
        subs = list(cache.get(path, []))
        if not subs and self.player.current_file == path:
            subs = list(self.player.current_subtitles)
        if not subs:
            return 0.0
        return max(subtitle.end_time for subtitle in subs)

    def _write_auto_srt(self, audio_path: str, subtitles: list[Subtitle]) -> None:
        output_path = Path(get_auto_srt_file_path(audio_path))
        try:
            with output_path.open("w", encoding="utf-8") as srt_file:
                for index, subtitle in enumerate(subtitles, start=1):
                    if not subtitle.text.strip():
                        continue
                    srt_file.write(
                        f"{index}\n"
                        f"{format_time(subtitle.start_time)} --> {format_time(subtitle.end_time)}\n"
                        f"{subtitle.text.strip()}\n\n"
                    )
        except Exception:
            # Keep subtitle rendering resilient even if persisting the sidecar fails.
            pass
