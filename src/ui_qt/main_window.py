"""Qt main window."""

from __future__ import annotations

import queue
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Optional

import pygame
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSlider,
    QSpinBox,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.audio_player import AudioPlayer
from src.core.subtitle_parser import Subtitle
from src.core.transcriber import Transcriber
from src.utils.config import Config
from src.utils.file_utils import find_audio_files
from src.utils.time_utils import format_timestamp


class SettingsDialog(QDialog):
    def __init__(self, config: Config, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Playback & AI Settings")
        self.resize(460, 360)

        form = QFormLayout(self)

        self.model_combo = QComboBox()
        self.model_combo.addItems(["base"])
        self.model_combo.setCurrentText("base")
        self.model_combo.setEnabled(False)

        self.device_combo = QComboBox()
        self.device_combo.addItems(["auto", "cuda", "cpu"])
        self.device_combo.setCurrentText(self.config.get("device", "auto"))

        self.language_combo = QComboBox()
        self.language_combo.setEditable(True)
        self.language_combo.addItems(["auto", "zh", "en", "ja", "ko"])
        self.language_combo.setCurrentText(self.config.get("whisper_language", "auto"))

        self.beam_spin = QSpinBox()
        self.beam_spin.setRange(1, 10)
        self.beam_spin.setValue(int(self.config.get("whisper_beam_size", 1)))

        self.best_of_spin = QSpinBox()
        self.best_of_spin.setRange(1, 10)
        self.best_of_spin.setValue(int(self.config.get("whisper_best_of", 1)))

        self.font_spin = QSpinBox()
        self.font_spin.setRange(12, 32)
        self.font_spin.setValue(int(self.config.get("subtitle_font_size", 14)))

        self.preview_chunk_spin = QSpinBox()
        self.preview_chunk_spin.setRange(8, 60)
        self.preview_chunk_spin.setValue(int(self.config.get("subtitle_preview_seconds", 20)))

        self.lead_spin = QSpinBox()
        self.lead_spin.setRange(4, 30)
        self.lead_spin.setValue(int(self.config.get("subtitle_chunk_lead_seconds", 12)))

        self.base_chunk_spin = QSpinBox()
        self.base_chunk_spin.setRange(15, 120)
        self.base_chunk_spin.setValue(int(self.config.get("base_chunk_seconds", 45)))

        self.upgrade_start_spin = QSpinBox()
        self.upgrade_start_spin.setRange(15, 180)
        self.upgrade_start_spin.setValue(int(self.config.get("upgrade_start_after_seconds", 60)))

        self.auto_checkbox = QCheckBox("Auto-transcribe on play")
        self.auto_checkbox.setChecked(bool(self.config.get("auto_transcribe_on_play", True)))

        self.full_checkbox = QCheckBox("Upgrade to base quality in background")
        self.full_checkbox.setChecked(bool(self.config.get("enable_full_transcription", True)))

        form.addRow("Whisper Model", self.model_combo)
        form.addRow("Device Mode", self.device_combo)
        form.addRow("Language", self.language_combo)
        form.addRow("Beam Size", self.beam_spin)
        form.addRow("Best Of", self.best_of_spin)
        form.addRow("Subtitle Font", self.font_spin)
        form.addRow("Tiny Chunk (s)", self.preview_chunk_spin)
        form.addRow("Chunk Lead (s)", self.lead_spin)
        form.addRow("Base Chunk (s)", self.base_chunk_spin)
        form.addRow("Upgrade Start (s)", self.upgrade_start_spin)
        form.addRow("", self.auto_checkbox)
        form.addRow("", self.full_checkbox)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def apply(self) -> None:
        self.config.set("whisper_model", self.model_combo.currentText())
        self.config.set("subtitle_preview_model", "base")
        self.config.set("device", self.device_combo.currentText())
        self.config.set("whisper_language", self.language_combo.currentText().strip() or "auto")
        self.config.set("whisper_beam_size", int(self.beam_spin.value()))
        self.config.set("whisper_best_of", int(self.best_of_spin.value()))
        self.config.set("subtitle_font_size", int(self.font_spin.value()))
        self.config.set("subtitle_preview_seconds", int(self.preview_chunk_spin.value()))
        self.config.set("subtitle_chunk_lead_seconds", int(self.lead_spin.value()))
        self.config.set("base_chunk_seconds", int(self.base_chunk_spin.value()))
        self.config.set("upgrade_start_after_seconds", int(self.upgrade_start_spin.value()))
        self.config.set("auto_transcribe_on_play", bool(self.auto_checkbox.isChecked()))
        self.config.set("enable_full_transcription", bool(self.full_checkbox.isChecked()))
        self.config.save()


class MainWindow(QMainWindow):
    subtitle_signal = Signal(object)
    position_signal = Signal(float)
    transcribe_done_signal = Signal(str, object, str)
    playback_end_signal = Signal()
    transcriber_info_signal = Signal(str)

    def __init__(self):
        app = QApplication.instance()
        self._app = app if app else QApplication([])
        super().__init__()

        self.config = Config()
        # Stabilize transcription pipeline: force single-model mode.
        self.config.set("whisper_model", "base")
        self.config.set("subtitle_preview_model", "base")
        self.player = AudioPlayer()
        self.transcriber = Transcriber()

        self.player.on_subtitle_changed = self._on_subtitle_changed
        self.player.on_position_changed = self._on_position_changed
        self.player.on_playback_end = self._on_playback_end
        self.player.on_subtitle_needed = self._on_subtitle_needed

        self.subtitle_signal.connect(self._apply_subtitle)
        self.position_signal.connect(self._apply_position)
        self.transcribe_done_signal.connect(self._on_transcribe_done)
        self.playback_end_signal.connect(self._handle_playback_end)
        self.transcriber_info_signal.connect(self._append_log)
        self.transcriber.on_info = lambda message: self.transcriber_info_signal.emit(message)

        self._lock = threading.Lock()
        self._current_generation = 0
        self._active_path: Optional[str] = None
        self._was_playing_track: bool = False
        self._handling_auto_next: bool = False
        self._closing_ui: bool = False
        self._loading_folder: bool = False
        self._transcribing_paths: set[str] = set()
        self._inflight: set[tuple[str, int, str, int]] = set()
        self._tiny_next_start: dict[str, int] = {}
        self._base_next_start: dict[str, int] = {}

        self._urgent_queue: "queue.Queue[Optional[dict]]" = queue.Queue()
        self._bg_queue: "queue.Queue[Optional[dict]]" = queue.Queue()
        self._worker_stop = threading.Event()
        self._worker = threading.Thread(target=self._transcription_worker, daemon=True)
        self._worker.start()

        self._last_subtitle_text: str = ""
        self._last_status_text: str = ""
        self._status_active: bool = False
        self._current_sub_key: Optional[tuple[float, float]] = None
        self._current_block_no: Optional[int] = None

        self._fmt_current = QTextCharFormat()
        self._fmt_current.setForeground(QColor("#f4f8ff"))
        self._fmt_current.setFontWeight(QFont.Bold)

        self._fmt_past = QTextCharFormat()
        self._fmt_past.setForeground(QColor("#8aa3c7"))
        self._fmt_past.setFontWeight(QFont.Normal)

        self._fmt_status = QTextCharFormat()
        self._fmt_status.setForeground(QColor("#9fb0c7"))
        self._fmt_status.setFontWeight(QFont.Normal)

        self._build_ui()
        self._apply_theme()

        self._scheduler = QTimer(self)
        self._scheduler.setInterval(500)
        self._scheduler.timeout.connect(self._tick_transcription_scheduler)
        self._scheduler.start()

        self.setWindowTitle("WinApp Audio Studio")
        self.resize(1100, 760)

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        self.title_label = QLabel("WinApp Audio Studio")
        self.title_label.setStyleSheet("font-size:24px;font-weight:700;color:#f2f6ff;")
        layout.addWidget(self.title_label)

        self.subtitle_box = QTextEdit()
        self.subtitle_box.setReadOnly(True)
        self.subtitle_box.setMinimumHeight(260)
        self.subtitle_box.setLineWrapMode(QTextEdit.WidgetWidth)
        self.subtitle_box.setFont(QFont("Microsoft YaHei UI", max(14, int(self.config.get("subtitle_font_size", 14)))))
        layout.addWidget(self.subtitle_box)

        self.time_label = QLabel("00:00:00 / 00:00:00")
        layout.addWidget(self.time_label)

        self.progress = QSlider(Qt.Horizontal)
        self.progress.setEnabled(False)
        layout.addWidget(self.progress)

        row = QHBoxLayout()
        self.btn_open = QPushButton("Open Folder")
        self.btn_prev = QPushButton("Prev")
        self.btn_play = QPushButton("Play")
        self.btn_next = QPushButton("Next")
        self.btn_settings = QPushButton("Settings")
        row.addWidget(self.btn_open)
        row.addWidget(self.btn_prev)
        row.addWidget(self.btn_play)
        row.addWidget(self.btn_next)
        row.addWidget(self.btn_settings)
        row.addStretch(1)
        row.addWidget(QLabel("Volume"))
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(100)
        row.addWidget(self.volume)
        layout.addLayout(row)

        self.playlist = QTreeWidget()
        self.playlist.setHeaderLabels(["#", "Track", "Duration", "Subtitles", "Task"])
        self.playlist.setRootIsDecorated(False)
        self.playlist.setAlternatingRowColors(True)
        self.playlist.setColumnWidth(0, 44)
        self.playlist.setColumnWidth(1, 360)
        self.playlist.setColumnWidth(2, 92)
        self.playlist.setColumnWidth(3, 90)
        self.playlist.setColumnWidth(4, 100)
        self.playlist.setMinimumHeight(420)
        layout.addWidget(self.playlist, 1)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(60)
        self.log.setMaximumHeight(80)
        layout.addWidget(self.log)

        self.btn_open.clicked.connect(self._open_folder)
        self.btn_play.clicked.connect(self._toggle_play)
        self.btn_prev.clicked.connect(self._prev)
        self.btn_next.clicked.connect(self._next)
        self.playlist.itemDoubleClicked.connect(self._play_item)
        self.btn_settings.clicked.connect(self._open_settings)
        self.volume.valueChanged.connect(lambda v: self.player.set_volume(v / 100.0))

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background: #0f172a; }
            QLabel { color: #d5e1ff; }
            QPushButton { background: #1f3d67; color: #e8f1ff; border: 1px solid #325f96; border-radius: 8px; padding: 6px 10px; font-weight: 600; }
            QPushButton:hover { background: #285084; }
            QTextEdit { background: #0e1a2f; color: #f4f8ff; border: 1px solid #2c4e7e; border-radius: 8px; }
            QTreeWidget { background: #0f1d35; color: #e6eeff; border: 1px solid #2a4a78; border-radius: 8px; alternate-background-color: #13233d; }
            QSlider::groove:horizontal { height: 6px; background: #24406b; border-radius: 3px; }
            QSlider::handle:horizontal { width: 14px; margin: -5px 0; border-radius: 7px; background: #66b6ff; border: 1px solid #9fd4ff; }
            QDialog { background: #111c32; color: #d5e1ff; }
            QComboBox, QSpinBox { background: #0f1d35; color: #e6eeff; border: 1px solid #325f96; border-radius: 6px; padding: 4px; }
            """
        )

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.config, self)
        if dlg.exec() == QDialog.Accepted:
            dlg.apply()
            self.subtitle_box.setFont(QFont("Microsoft YaHei UI", max(14, int(self.config.get("subtitle_font_size", 14)))))
            self.log.append("Settings saved")

    def _open_folder(self) -> None:
        self._loading_folder = True
        try:
            # Stop current playback and transcription when loading a new folder.
            self._cancel_active_transcription()
            self.player.stop()
            self.player.current_file = None
            self.player.current_subtitles = []
            self._active_path = None
            self._was_playing_track = False

            directory = QFileDialog.getExistingDirectory(self, "Select Folder")
            if not directory:
                self._reset_playback_ui()
                return

            files = find_audio_files(
                directory,
                extensions=self.config.get("supported_formats", [".mp3", ".m4a", ".wav", ".wma"]),
            )
            self.player.set_playlist(files)
            self.playlist.clear()
            self._reset_playback_ui()

            for i, f in enumerate(files, start=1):
                subtitle_state = "Ready" if self.player.has_subtitles(f) else "Missing"
                item = QTreeWidgetItem([str(i), Path(f).name, "--:--", subtitle_state, "Idle"])
                item.setData(0, Qt.UserRole, f)
                self.playlist.addTopLevelItem(item)

            if files:
                self.player.current_index = 0
                self.playlist.setCurrentItem(self.playlist.topLevelItem(0))
                self.log.append(f"Loaded {len(files)} tracks")
            else:
                self.player.current_index = -1
                self.log.append("No audio files found in selected folder")
        finally:
            self._loading_folder = False

    def _reset_playback_ui(self) -> None:
        self.subtitle_box.clear()
        self._last_subtitle_text = ""
        self._last_status_text = ""
        self._status_active = False
        self._current_sub_key = None
        self._current_block_no = None
        self.progress.setValue(0)
        self.progress.setEnabled(False)
        self.time_label.setText("00:00:00 / 00:00:00")
        self.btn_play.setText("Play")
        self._was_playing_track = False

    def _toggle_play(self) -> None:
        if not self.player.is_playing and not self.player.is_paused:
            if self.player.playlist and self.player.current_index >= 0:
                self._play_index(self.player.current_index)
            return
        self.player.toggle_pause()
        self.btn_play.setText("Play" if self.player.is_paused else "Pause")

    def _play_item(self, item, _column) -> None:
        self._play_index(self.playlist.indexOfTopLevelItem(item))

    def _prev(self) -> None:
        if not self.player.playlist:
            return
        i = self.player.current_index - 1 if self.player.current_index > 0 else len(self.player.playlist) - 1
        self._play_index(i)

    def _next(self) -> None:
        if self._closing_ui or self._loading_folder:
            return
        if not self.player.playlist:
            return
        i = self.player.current_index + 1 if self.player.current_index < len(self.player.playlist) - 1 else 0
        self._play_index(i)

    def _play_index(self, index: int) -> None:
        if self._closing_ui or self._loading_folder:
            return
        if not (0 <= index < len(self.player.playlist)):
            return

        self._cancel_active_transcription()

        self.player.current_index = index
        path = self.player.playlist[index]
        if not self.player.play(path):
            self.log.append("Play failed")
            return

        self._active_path = path
        self.subtitle_box.clear()
        self._last_subtitle_text = ""
        self._last_status_text = ""
        self._status_active = False
        self._current_sub_key = None
        self._current_block_no = None

        current_item = self.playlist.topLevelItem(index)
        if current_item is not None:
            self.playlist.setCurrentItem(current_item)

        self.btn_play.setText("Pause")
        self.progress.setEnabled(True)
        self.progress.setRange(0, max(1, int(self.player.current_duration * 1000)))
        self.time_label.setText(f"00:00:00 / {format_timestamp(self.player.current_duration)}")
        self._was_playing_track = True
        self._handling_auto_next = False

    def _cancel_active_transcription(self) -> None:
        with self._lock:
            self._current_generation += 1
            self._transcribing_paths.clear()
            self._inflight.clear()
            self._tiny_next_start.clear()
            self._base_next_start.clear()

        self._drain_queue(self._urgent_queue)
        self._drain_queue(self._bg_queue)

    @staticmethod
    def _drain_queue(q: "queue.Queue[Optional[dict]]") -> None:
        while True:
            try:
                q.get_nowait()
                q.task_done()
            except Exception:
                break

    def _on_subtitle_needed(self, audio_path: str) -> None:
        if not self.config.get("auto_transcribe_on_play", True):
            return
        if self.player.current_file != audio_path:
            return

        with self._lock:
            self._transcribing_paths.add(audio_path)
            if audio_path not in self._tiny_next_start:
                self._tiny_next_start[audio_path] = 0
            if audio_path not in self._base_next_start:
                self._base_next_start[audio_path] = 0
            generation = self._current_generation

        for i in range(self.playlist.topLevelItemCount()):
            row = self.playlist.topLevelItem(i)
            if row and row.data(0, Qt.UserRole) == audio_path:
                row.setText(4, "Run")
                break

        self._enqueue_chunk_job(
            path=audio_path,
            start_seconds=0,
            seconds=int(self.config.get("subtitle_preview_seconds", 20)),
            model="base",
            generation=generation,
            urgent=True,
        )

        status = "Generating subtitles..."
        if not self._status_active:
            self._append_subtitle_line(status, self._fmt_status)
            self._last_status_text = status
            self._status_active = True

    def _tick_transcription_scheduler(self) -> None:
        if self._closing_ui or self._loading_folder:
            return

        # Fallback watchdog: if playback stopped but callback was missed, advance to next track.
        if (
            self._was_playing_track
            and not self.player.is_playing
            and not self.player.is_paused
            and self.player.current_file
            and self.player.playlist
            and not self._handling_auto_next
        ):
            self._handle_playback_end()
            return

        # Secondary watchdog: mixer reports end but internal state did not transition.
        if (
            self._was_playing_track
            and self.player.is_playing
            and not self.player.is_paused
            and self.player.current_duration > 0
            and not self._handling_auto_next
        ):
            position = self.player.get_position()
            reached_tail = position >= (self.player.current_duration - 0.3)
            mixer_idle = not pygame.mixer.music.get_busy()
            if reached_tail and mixer_idle:
                self._handle_playback_end()
                return

        if not self.player.is_playing or self.player.is_paused:
            return

        path = self.player.current_file
        if not path:
            return

        with self._lock:
            if path not in self._transcribing_paths:
                return
            generation = self._current_generation
            tiny_next = int(self._tiny_next_start.get(path, 0))
            base_next = int(self._base_next_start.get(path, 0))

        position = self.player.get_position()
        lead_seconds = int(self.config.get("subtitle_chunk_lead_seconds", 12))
        tiny_chunk = int(self.config.get("subtitle_preview_seconds", 20))
        base_chunk = int(self.config.get("base_chunk_seconds", 45))
        upgrade_start = int(self.config.get("upgrade_start_after_seconds", 60))

        if int(position + lead_seconds) >= tiny_next:
            self._enqueue_chunk_job(
                path=path,
                start_seconds=tiny_next,
                seconds=tiny_chunk,
                model="base",
                generation=generation,
                urgent=True,
            )
            with self._lock:
                self._tiny_next_start[path] = tiny_next + tiny_chunk

        if not self.config.get("enable_full_transcription", True):
            return

        tiny_covered = self._get_cached_coverage(path)
        if tiny_covered < upgrade_start:
            return

        if int(position + lead_seconds) >= base_next and (base_next + base_chunk) <= int(tiny_covered + 1):
            self._enqueue_chunk_job(
                path=path,
                start_seconds=base_next,
                seconds=base_chunk,
                model="base",
                generation=generation,
                urgent=False,
            )
            with self._lock:
                self._base_next_start[path] = base_next + base_chunk

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
            model = str(job.get("model", "tiny"))
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
                    model_name="base",
                    device=self.config.get("device", "auto"),
                    **kwargs,
                )
            except Exception as exc:
                self.transcribe_done_signal.emit(path, str(exc), model)
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

            self.transcribe_done_signal.emit(path, None, model)
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
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                Path(tmp_path).unlink(missing_ok=True)
                return None
            return tmp_path
        except Exception:
            return None

    @staticmethod
    def _offset_subtitles(subtitles: list[Subtitle], offset: float) -> list[Subtitle]:
        out: list[Subtitle] = []
        for i, s in enumerate(subtitles, start=1):
            text = s.text.strip()
            if not text:
                continue
            out.append(
                Subtitle(
                    index=i,
                    start_time=s.start_time + offset,
                    end_time=s.end_time + offset,
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

        if model == "base":
            kept = [s for s in current if s.end_time < start_seconds or s.start_time > end_seconds]
            merged = kept + new_subs
        else:
            merged = current + new_subs

        merged.sort(key=lambda s: (s.start_time, s.end_time))
        dedup: list[Subtitle] = []
        last_key = None
        for s in merged:
            key = (round(s.start_time, 3), round(s.end_time, 3), s.text)
            if key == last_key:
                continue
            dedup.append(s)
            last_key = key
        return dedup

    def _get_cached_coverage(self, path: str) -> float:
        cache = getattr(self.player, "_subtitle_cache", {})
        subs = list(cache.get(path, []))
        if not subs and self.player.current_file == path:
            subs = list(self.player.current_subtitles)
        if not subs:
            return 0.0
        return max(s.end_time for s in subs)

    def _on_transcribe_done(self, path: str, error: Optional[str], model: str) -> None:
        for i in range(self.playlist.topLevelItemCount()):
            row = self.playlist.topLevelItem(i)
            if row and row.data(0, Qt.UserRole) == path:
                if error:
                    row.setText(4, "Fail")
                else:
                    row.setText(3, "Ready")
                    row.setText(4, "Base")
                break

        if error:
            self.log.append(f"[{model}] Transcription failed: {error}")

    def _append_log(self, message: str) -> None:
        self.log.append(message)

    def _on_subtitle_changed(self, subtitle: Optional[Subtitle]) -> None:
        self.subtitle_signal.emit(subtitle)

    def _apply_subtitle(self, subtitle_obj: object) -> None:
        subtitle = subtitle_obj if isinstance(subtitle_obj, Subtitle) else None
        if subtitle is None:
            if self.player.current_file and self._is_transcribing(self.player.current_file):
                status = "Generating subtitles..."
                if not self._status_active:
                    self._append_subtitle_line(status, self._fmt_status)
                    self._last_status_text = status
                    self._status_active = True
            return

        self._last_status_text = ""
        if self._status_active:
            self.subtitle_box.clear()
            self._status_active = False
            self._current_sub_key = None
            self._current_block_no = None

        text = subtitle.text.strip()
        if not text:
            return

        current_key = (round(subtitle.start_time, 2), round(subtitle.end_time, 2))

        if self._current_sub_key == current_key and self._current_block_no is not None:
            if text != self._last_subtitle_text:
                self._replace_block_text(self._current_block_no, text, self._fmt_current)
                self._last_subtitle_text = text
            return

        if self._current_block_no is not None:
            self._apply_format_to_block(self._current_block_no, self._fmt_past)

        self._current_block_no = self._append_subtitle_line(text, self._fmt_current)
        self._current_sub_key = current_key
        self._last_subtitle_text = text

    def _append_subtitle_line(self, text: str, fmt: QTextCharFormat) -> int:
        doc = self.subtitle_box.document()
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.End)

        if doc.toPlainText().strip():
            cursor.insertBlock()

        cursor.insertText(text, fmt)
        self.subtitle_box.setTextCursor(cursor)
        self.subtitle_box.ensureCursorVisible()
        return cursor.block().blockNumber()

    def _apply_format_to_block(self, block_no: int, fmt: QTextCharFormat) -> None:
        block = self.subtitle_box.document().findBlockByNumber(block_no)
        if not block.isValid():
            return
        cursor = QTextCursor(block)
        cursor.select(QTextCursor.BlockUnderCursor)
        cursor.setCharFormat(fmt)

    def _replace_block_text(self, block_no: int, text: str, fmt: QTextCharFormat) -> None:
        block = self.subtitle_box.document().findBlockByNumber(block_no)
        if not block.isValid():
            return
        cursor = QTextCursor(block)
        cursor.select(QTextCursor.BlockUnderCursor)
        cursor.removeSelectedText()
        cursor.insertText(text, fmt)

    def _on_position_changed(self, position: float) -> None:
        self.position_signal.emit(position)

    def _apply_position(self, position: float) -> None:
        self.progress.setValue(int(position * 1000))
        self.time_label.setText(f"{format_timestamp(position)} / {format_timestamp(self.player.current_duration)}")

    def _on_playback_end(self) -> None:
        if self._closing_ui or self._loading_folder:
            return
        self.position_signal.emit(self.player.current_duration)
        self.playback_end_signal.emit()

    def _handle_playback_end(self) -> None:
        if self._closing_ui or self._loading_folder:
            return
        if self._handling_auto_next:
            return

        self._handling_auto_next = True
        self._was_playing_track = False
        try:
            self._next()
        finally:
            self._handling_auto_next = False

    def _is_transcribing(self, path: str) -> bool:
        with self._lock:
            if path not in self._transcribing_paths:
                return False
            for inflight_path, _start, _model, _gen in self._inflight:
                if inflight_path == path:
                    return True
            return False

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._closing_ui = True
        try:
            self._scheduler.stop()
        except Exception:
            pass

        self.player.on_subtitle_changed = None
        self.player.on_position_changed = None
        self.player.on_playback_end = None
        self.player.on_subtitle_needed = None

        self._worker_stop.set()
        try:
            self._urgent_queue.put_nowait(None)
        except Exception:
            pass
        try:
            self._bg_queue.put_nowait(None)
        except Exception:
            pass
        self.player.cleanup()
        super().closeEvent(event)

    def run(self) -> None:
        self.show()
        self._app.exec()
