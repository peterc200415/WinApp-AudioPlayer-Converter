"""Qt main window."""

from __future__ import annotations

import subprocess
import tempfile
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
    QMessageBox,
    QProgressDialog,
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
from src.core.track_rename_service import RenamePreview, TrackRenameService
from src.core.transcriber import Transcriber
from src.core.transcription_manager import TranscriptionManager
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
        self.model_combo.setCurrentText(self.config.get("whisper_model", "base"))
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
        form.addRow("Preview Chunk (s)", self.preview_chunk_spin)
        form.addRow("Chunk Lead (s)", self.lead_spin)
        form.addRow("Upgrade Chunk (s)", self.base_chunk_spin)
        form.addRow("Upgrade Start (s)", self.upgrade_start_spin)
        form.addRow("", self.auto_checkbox)
        form.addRow("", self.full_checkbox)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def apply(self) -> None:
        model_name = self.model_combo.currentText()
        self.config.set("whisper_model", model_name)
        self.config.set("subtitle_preview_model", model_name)
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


class RenamePreviewDialog(QDialog):
    def __init__(
        self,
        previews: list[RenamePreview],
        rename_service: TrackRenameService,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.previews = previews
        self.rename_service = rename_service
        self.applied_changes: list[tuple[str, str]] = []

        self.setWindowTitle("Identify & Rename Tracks")
        self.resize(980, 520)

        layout = QVBoxLayout(self)

        hint = QLabel("Review the suggested source match and filename before applying changes.")
        layout.addWidget(hint)

        self.table = QTreeWidget()
        self.table.setHeaderLabels(["Current File", "Detected Query", "Matched Source", "Suggested Name", "Status"])
        self.table.setRootIsDecorated(False)
        self.table.setAlternatingRowColors(True)
        self.table.setColumnWidth(0, 230)
        self.table.setColumnWidth(1, 220)
        self.table.setColumnWidth(2, 220)
        self.table.setColumnWidth(3, 240)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table, 1)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        self.apply_button = QPushButton("Apply Rename")
        buttons.addButton(self.apply_button, QDialogButtonBox.AcceptRole)
        buttons.rejected.connect(self.reject)
        self.apply_button.clicked.connect(self._apply_selected)
        layout.addWidget(buttons)

        self._populate()

    def _populate(self) -> None:
        for preview in self.previews:
            match = preview.match
            source = ""
            suggestion = ""
            status = preview.error or "Ready"
            if match is not None:
                release_text = f" / {match.release}" if match.release else ""
                source = f"{match.artist} - {match.title}{release_text}"
                suggestion = match.suggested_name
                status = match.reason

            item = QTreeWidgetItem(
                [
                    preview.current_name,
                    preview.detected_query or "(empty)",
                    source or "(no match)",
                    suggestion,
                    status,
                ]
            )
            item.setCheckState(0, Qt.Checked if match is not None else Qt.Unchecked)
            item.setData(0, Qt.UserRole, preview)
            if match is None:
                item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
            self.table.addTopLevelItem(item)

        self._refresh_summary()

    def _refresh_summary(self) -> None:
        total = len(self.previews)
        matched = 0
        no_match = 0
        selected = 0
        renamed = 0
        failed = 0

        for index in range(self.table.topLevelItemCount()):
            item = self.table.topLevelItem(index)
            preview = item.data(0, Qt.UserRole)
            if not isinstance(preview, RenamePreview):
                continue

            status = item.text(4)
            if preview.match is not None:
                matched += 1
            else:
                no_match += 1

            if item.checkState(0) == Qt.Checked:
                selected += 1
            if status == "Renamed":
                renamed += 1
            if status.startswith("Rename failed:"):
                failed += 1

        self.summary.setText(
            f"Total: {total} | Matched: {matched} | No Match: {no_match} | "
            f"Selected: {selected} | Renamed: {renamed} | Failed: {failed}"
        )
        self.apply_button.setEnabled(selected > 0)

    def _on_item_changed(self, _item: QTreeWidgetItem, _column: int) -> None:
        self._refresh_summary()

    def _apply_selected(self) -> None:
        applied = 0
        failures = []
        attempted = 0
        for index in range(self.table.topLevelItemCount()):
            item = self.table.topLevelItem(index)
            preview = item.data(0, Qt.UserRole)
            if not isinstance(preview, RenamePreview):
                continue
            if preview.match is None or item.checkState(0) != Qt.Checked:
                continue
            attempted += 1
            try:
                new_path = self.rename_service.apply_rename(preview)
            except Exception as exc:
                failures.append(f"{preview.current_name}: {exc}")
                item.setText(4, f"Rename failed: {exc}")
                continue

            applied += 1
            self.applied_changes.append((preview.path, new_path))
            preview.path = new_path
            preview.current_name = Path(new_path).name
            item.setText(0, preview.current_name)
            item.setText(4, "Renamed")
            item.setCheckState(0, Qt.Unchecked)

        self._refresh_summary()

        if parent := self.parent():
            if hasattr(parent, "_append_log"):
                parent._append_log(f"Rename apply finished: {applied}/{attempted} succeeded")
            for message in failures[:10]:
                if hasattr(parent, "_append_log"):
                    parent._append_log(f"[Rename] {message}")

        if failures:
            QMessageBox.warning(self, "Rename Completed With Errors", "\n".join(failures[:10]))
        elif applied:
            QMessageBox.information(self, "Rename Completed", f"Renamed {applied} track(s).")
        else:
            QMessageBox.information(self, "No Changes", "No selected tracks were renamed.")


class MainWindow(QMainWindow):
    subtitle_signal = Signal(object)
    position_signal = Signal(float)
    playback_end_signal = Signal()
    transcriber_info_signal = Signal(str)
    transcription_started_signal = Signal(str)
    transcription_ready_signal = Signal(str, str)
    transcription_failed_signal = Signal(str, str, str)

    def __init__(self):
        app = QApplication.instance()
        self._app = app if app else QApplication([])
        super().__init__()

        self.config = Config()
        self.player = AudioPlayer()
        self.transcriber = Transcriber()
        self.rename_service = TrackRenameService()
        self.transcription_manager = TranscriptionManager(self.player, self.transcriber, self.config)

        self.player.on_subtitle_changed = self._on_subtitle_changed
        self.player.on_position_changed = self._on_position_changed
        self.player.on_playback_end = self._on_playback_end
        self.player.on_subtitle_needed = self._on_subtitle_needed

        self.subtitle_signal.connect(self._apply_subtitle)
        self.position_signal.connect(self._apply_position)
        self.playback_end_signal.connect(self._handle_playback_end)
        self.transcriber_info_signal.connect(self._append_log)
        self.transcription_started_signal.connect(self._on_transcription_started)
        self.transcription_ready_signal.connect(self._on_transcription_ready)
        self.transcription_failed_signal.connect(self._on_transcription_failed)

        self.transcriber.on_info = lambda message: self.transcriber_info_signal.emit(message)
        self.transcription_manager.on_transcription_started = (
            lambda path: self.transcription_started_signal.emit(path)
        )
        self.transcription_manager.on_transcription_ready = (
            lambda path, model: self.transcription_ready_signal.emit(path, model)
        )
        self.transcription_manager.on_transcription_failed = (
            lambda path, model, error: self.transcription_failed_signal.emit(path, model, error)
        )

        self._active_path: Optional[str] = None
        self._was_playing_track = False
        self._handling_auto_next = False
        self._closing_ui = False
        self._loading_folder = False

        self._last_subtitle_text = ""
        self._last_status_text = ""
        self._status_active = False
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
        self._scheduler.timeout.connect(self._tick)
        self._scheduler.start()

        self.setWindowTitle("WinApp Audio Studio")
        self.resize(980, 700)

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        header_row = QHBoxLayout()
        header_row.setSpacing(12)
        header_stack = QVBoxLayout()
        header_stack.setSpacing(2)
        self.title_label = QLabel("WinApp Audio Studio")
        self.title_label.setObjectName("heroTitle")
        self.hero_subtitle = QLabel("Play, subtitle, identify, and rename your tracks in one place.")
        self.hero_subtitle.setObjectName("heroSubtitle")
        header_stack.addWidget(self.title_label)
        header_stack.addWidget(self.hero_subtitle)
        header_row.addLayout(header_stack, 1)

        self.badge_label = QLabel("Desktop Mix")
        self.badge_label.setObjectName("heroBadge")
        self.badge_label.setAlignment(Qt.AlignCenter)
        header_row.addWidget(self.badge_label)

        self.btn_theme = QPushButton()
        self.btn_theme.setObjectName("themeToggle")
        self.btn_theme.clicked.connect(self._toggle_theme)
        header_row.addWidget(self.btn_theme)
        layout.addLayout(header_row)

        now_playing_card = QWidget()
        now_playing_card.setObjectName("card")
        now_playing_layout = QVBoxLayout(now_playing_card)
        now_playing_layout.setContentsMargins(18, 18, 18, 16)
        now_playing_layout.setSpacing(10)
        now_playing_title = QLabel("Now Playing")
        now_playing_title.setObjectName("sectionTitle")
        now_playing_layout.addWidget(now_playing_title)

        self.subtitle_box = QTextEdit()
        self.subtitle_box.setReadOnly(True)
        self.subtitle_box.setMinimumHeight(180)
        self.subtitle_box.setMaximumHeight(240)
        self.subtitle_box.setLineWrapMode(QTextEdit.WidgetWidth)
        self.subtitle_box.setFont(
            QFont("Microsoft YaHei UI", max(14, int(self.config.get("subtitle_font_size", 14))))
        )
        self.subtitle_box.setObjectName("subtitleBox")
        now_playing_layout.addWidget(self.subtitle_box)

        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.time_label.setObjectName("timeLabel")
        now_playing_layout.addWidget(self.time_label)

        self.progress = QSlider(Qt.Horizontal)
        self.progress.setEnabled(False)
        now_playing_layout.addWidget(self.progress)
        layout.addWidget(now_playing_card)

        controls_card = QWidget()
        controls_card.setObjectName("card")
        row = QHBoxLayout(controls_card)
        row.setContentsMargins(18, 14, 18, 14)
        row.setSpacing(10)
        self.btn_open = QPushButton("Open Folder")
        self.btn_prev = QPushButton("Prev")
        self.btn_play = QPushButton("Play")
        self.btn_next = QPushButton("Next")
        self.btn_rename = QPushButton("Identify & Rename")
        self.btn_settings = QPushButton("Settings")
        self.btn_play.setObjectName("primaryButton")
        self.btn_rename.setObjectName("accentButton")
        row.addWidget(self.btn_open)
        row.addWidget(self.btn_prev)
        row.addWidget(self.btn_play)
        row.addWidget(self.btn_next)
        row.addWidget(self.btn_rename)
        row.addWidget(self.btn_settings)
        row.addStretch(1)
        volume_label = QLabel("Volume")
        volume_label.setObjectName("mutedLabel")
        row.addWidget(volume_label)
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(100)
        self.volume.setMaximumWidth(150)
        row.addWidget(self.volume)
        layout.addWidget(controls_card)

        library_card = QWidget()
        library_card.setObjectName("card")
        library_layout = QVBoxLayout(library_card)
        library_layout.setContentsMargins(18, 18, 18, 16)
        library_layout.setSpacing(10)
        library_title = QLabel("Library")
        library_title.setObjectName("sectionTitle")
        library_layout.addWidget(library_title)

        self.playlist = QTreeWidget()
        self.playlist.setHeaderLabels(["#", "Track", "Duration", "Subtitles", "Task"])
        self.playlist.setRootIsDecorated(False)
        self.playlist.setAlternatingRowColors(True)
        self.playlist.setColumnWidth(0, 44)
        self.playlist.setColumnWidth(1, 320)
        self.playlist.setColumnWidth(2, 92)
        self.playlist.setColumnWidth(3, 90)
        self.playlist.setColumnWidth(4, 100)
        self.playlist.setMinimumHeight(280)
        self.playlist.setMaximumHeight(360)
        library_layout.addWidget(self.playlist)
        layout.addWidget(library_card, 1)

        log_card = QWidget()
        log_card.setObjectName("card")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(18, 16, 18, 14)
        log_layout.setSpacing(8)
        log_title = QLabel("Activity")
        log_title.setObjectName("sectionTitle")
        log_layout.addWidget(log_title)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(88)
        self.log.setMaximumHeight(112)
        self.log.setObjectName("logBox")
        log_layout.addWidget(self.log)
        layout.addWidget(log_card)

        self.btn_open.clicked.connect(self._open_folder)
        self.btn_play.clicked.connect(self._toggle_play)
        self.btn_prev.clicked.connect(self._prev)
        self.btn_next.clicked.connect(self._next)
        self.btn_rename.clicked.connect(self._identify_and_rename_tracks)
        self.playlist.itemDoubleClicked.connect(self._play_item)
        self.btn_settings.clicked.connect(self._open_settings)
        self.volume.valueChanged.connect(lambda v: self.player.set_volume(v / 100.0))
        self._sync_theme_button()

    def _apply_theme(self) -> None:
        theme = str(self.config.get("theme", "light")).lower()
        self.setStyleSheet(self._dark_theme_stylesheet() if theme == "dark" else self._light_theme_stylesheet())
        self._sync_theme_button()

    def _light_theme_stylesheet(self) -> str:
        return """
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #fff5ef, stop:0.45 #ffe5da, stop:1 #ffd8cc);
            }
            QWidget#card {
                background: rgba(255, 252, 248, 0.92);
                border: 1px solid rgba(236, 181, 158, 0.72);
                border-radius: 18px;
            }
            QLabel { color: #4d2f38; }
            QLabel#heroTitle { font-size: 30px; font-weight: 800; color: #2d1d2f; }
            QLabel#heroSubtitle { font-size: 13px; color: #8f5f65; }
            QLabel#heroBadge {
                background: #ff7f50; color: white; border-radius: 14px;
                padding: 8px 14px; font-size: 12px; font-weight: 700;
            }
            QLabel#sectionTitle { font-size: 15px; font-weight: 700; color: #5e3043; }
            QLabel#mutedLabel, QLabel#timeLabel { color: #93656c; font-size: 12px; }
            QPushButton {
                background: #ffffff; color: #4d2f38; border: 1px solid #efb19a;
                border-radius: 12px; padding: 8px 14px; font-weight: 700;
            }
            QPushButton:hover { background: #fff3ee; }
            QPushButton#primaryButton { background: #ff8c61; color: #ffffff; border: 1px solid #ff8c61; }
            QPushButton#primaryButton:hover { background: #ff7a4c; }
            QPushButton#accentButton { background: #ffd166; color: #4d2f38; border: 1px solid #f2bf3d; }
            QPushButton#accentButton:hover { background: #ffca4a; }
            QPushButton#themeToggle {
                background: rgba(255,255,255,0.78); color: #4d2f38; min-width: 108px;
            }
            QTextEdit, QTreeWidget {
                background: rgba(255, 255, 255, 0.9); color: #402830; border: 1px solid #f0c4b1;
                border-radius: 14px; alternate-background-color: #fff7f3;
            }
            QTextEdit#subtitleBox { font-size: 15px; }
            QTextEdit#logBox { color: #6b4750; }
            QHeaderView::section {
                background: #fff0e8; color: #7d4d5a; border: none; padding: 8px; font-weight: 700;
            }
            QSlider::groove:horizontal { height: 8px; background: #f6c7b3; border-radius: 4px; }
            QSlider::handle:horizontal {
                width: 18px; margin: -6px 0; border-radius: 9px; background: #ff7f50; border: 2px solid #ffffff;
            }
            QDialog { background: #fff8f4; color: #4d2f38; }
            QComboBox, QSpinBox {
                background: #ffffff; color: #4d2f38; border: 1px solid #efb19a;
                border-radius: 10px; padding: 6px 8px;
            }
        """

    def _dark_theme_stylesheet(self) -> str:
        return """
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #131722, stop:0.55 #1a2030, stop:1 #242030);
            }
            QWidget#card {
                background: rgba(27, 33, 49, 0.94);
                border: 1px solid rgba(88, 102, 143, 0.72);
                border-radius: 18px;
            }
            QLabel { color: #e9edf7; }
            QLabel#heroTitle { font-size: 30px; font-weight: 800; color: #ffffff; }
            QLabel#heroSubtitle { font-size: 13px; color: #aab4d0; }
            QLabel#heroBadge {
                background: #7c5cff; color: white; border-radius: 14px;
                padding: 8px 14px; font-size: 12px; font-weight: 700;
            }
            QLabel#sectionTitle { font-size: 15px; font-weight: 700; color: #f3f6ff; }
            QLabel#mutedLabel, QLabel#timeLabel { color: #a2adcb; font-size: 12px; }
            QPushButton {
                background: #242d44; color: #f0f4ff; border: 1px solid #445174;
                border-radius: 12px; padding: 8px 14px; font-weight: 700;
            }
            QPushButton:hover { background: #2d3752; }
            QPushButton#primaryButton { background: #ff8c61; color: #ffffff; border: 1px solid #ff8c61; }
            QPushButton#primaryButton:hover { background: #ff7a4c; }
            QPushButton#accentButton { background: #7c5cff; color: #ffffff; border: 1px solid #7c5cff; }
            QPushButton#accentButton:hover { background: #6b4df0; }
            QPushButton#themeToggle {
                background: rgba(36,45,68,0.9); color: #f0f4ff; min-width: 108px;
            }
            QTextEdit, QTreeWidget {
                background: rgba(18, 24, 38, 0.9); color: #edf2ff; border: 1px solid #3b486c;
                border-radius: 14px; alternate-background-color: #1b2438;
            }
            QTextEdit#subtitleBox { font-size: 15px; }
            QTextEdit#logBox { color: #c5d0ef; }
            QHeaderView::section {
                background: #232c43; color: #d7e1ff; border: none; padding: 8px; font-weight: 700;
            }
            QSlider::groove:horizontal { height: 8px; background: #36425f; border-radius: 4px; }
            QSlider::handle:horizontal {
                width: 18px; margin: -6px 0; border-radius: 9px; background: #7c5cff; border: 2px solid #ffffff;
            }
            QDialog { background: #1a2131; color: #edf2ff; }
            QComboBox, QSpinBox {
                background: #20293d; color: #edf2ff; border: 1px solid #445174;
                border-radius: 10px; padding: 6px 8px;
            }
        """

    def _toggle_theme(self) -> None:
        next_theme = "dark" if str(self.config.get("theme", "light")).lower() == "light" else "light"
        self.config.set("theme", next_theme)
        self.config.save()
        self._apply_theme()
        self._append_log(f"Theme switched to {next_theme}")

    def _sync_theme_button(self) -> None:
        if hasattr(self, "btn_theme"):
            is_dark = str(self.config.get("theme", "light")).lower() == "dark"
            self.btn_theme.setText("Light Mode" if is_dark else "Dark Mode")

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.config, self)
        if dlg.exec() == QDialog.Accepted:
            dlg.apply()
            self.subtitle_box.setFont(
                QFont("Microsoft YaHei UI", max(14, int(self.config.get("subtitle_font_size", 14))))
            )
            self.log.append("Settings saved")

    def _open_folder(self) -> None:
        self._loading_folder = True
        try:
            self.transcription_manager.cancel_active()
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

            for index, file_path in enumerate(files, start=1):
                subtitle_state = "Ready" if self.player.has_subtitles(file_path) else "Missing"
                item = QTreeWidgetItem([str(index), Path(file_path).name, "--:--", subtitle_state, "Idle"])
                item.setData(0, Qt.UserRole, file_path)
                self.playlist.addTopLevelItem(item)

            if files:
                self.player.current_index = 0
                self.playlist.setCurrentItem(self.playlist.topLevelItem(0))
                self.log.append(f"Loaded {len(files)} tracks")
            else:
                self.player.current_index = -1
                formats = ", ".join(self.config.get("supported_formats", []))
                self.log.append(f"No audio files found in selected folder. Scanned formats: {formats}")
        finally:
            self._loading_folder = False

    def _identify_and_rename_tracks(self) -> None:
        if not self.player.playlist:
            QMessageBox.information(self, "No Tracks", "Load a folder before identifying track sources.")
            return

        previews: list[RenamePreview] = []
        total = len(self.player.playlist)
        self._append_log(f"Looking up track sources online for {total} track(s)...")
        progress = QProgressDialog("Identifying tracks...", None, 0, total, self)
        progress.setWindowTitle("Identify & Rename")
        progress.setMinimumDuration(0)
        progress.setAutoClose(True)
        progress.setCancelButton(None)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        self.statusBar().showMessage("Identifying track sources...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for index, path in enumerate(self.player.playlist, start=1):
                file_name = Path(path).name
                progress.setLabelText(f"Checking {index}/{total}: {file_name}")
                progress.setValue(index - 1)
                QApplication.processEvents()

                preview = self.rename_service.build_preview(path)
                if preview.match is None:
                    fallback_preview = self._build_subtitle_match_preview(path)
                    if fallback_preview.match is not None:
                        preview = fallback_preview
                previews.append(preview)

                if preview.match is not None:
                    self._append_log(
                        f"[Identify {index}/{total}] {file_name} -> {preview.match.suggested_name}"
                    )
                else:
                    detail = preview.error or "No match found"
                    self._append_log(f"[Identify {index}/{total}] {file_name} -> {detail}")
        finally:
            progress.setValue(total)
            progress.close()
            QApplication.restoreOverrideCursor()
            self.statusBar().clearMessage()

        dialog = RenamePreviewDialog(previews, self.rename_service, self)
        dialog.exec()

        if not dialog.applied_changes:
            self._append_log("Rename preview closed without changes")
            return

        rename_map = {old_path: new_path for old_path, new_path in dialog.applied_changes}
        self.player.playlist = [rename_map.get(path, path) for path in self.player.playlist]
        if self.player.current_file in rename_map:
            self.player.current_file = rename_map[self.player.current_file]
        self._refresh_playlist_names()
        self._append_log(f"Renamed {len(dialog.applied_changes)} track(s)")

    def _build_subtitle_match_preview(self, path: str) -> RenamePreview:
        snippets = self._transcribe_subtitle_snippets(path)
        if not snippets:
            return RenamePreview(
                path=path,
                current_name=Path(path).name,
                detected_query="",
                match=None,
                error="No subtitle snippet available for fallback.",
            )

        preview = self.rename_service.build_preview_from_lyric_snippets(path, snippets)
        if preview.match is not None:
            self._append_log(f"[Subtitle Match] {Path(path).name} -> {preview.match.suggested_name}")
        return preview

    def _transcribe_subtitle_snippets(self, audio_path: str, seconds: int = 18) -> list[str]:
        duration = self._get_audio_duration_seconds(audio_path)
        starts = self._build_sample_offsets(duration, seconds)
        snippets: list[str] = []

        for start_seconds in starts:
            snippet = self._transcribe_subtitle_snippet(audio_path, start_seconds=start_seconds, seconds=seconds)
            if snippet and snippet not in snippets:
                snippets.append(snippet)
        return snippets

    def _transcribe_subtitle_snippet(self, audio_path: str, start_seconds: int = 0, seconds: int = 18) -> str:
        preview_wav = self._make_preview_wav(audio_path, start_seconds=start_seconds, seconds=seconds)
        if not preview_wav:
            return ""

        try:
            kwargs = {
                "beam_size": self.config.get("whisper_beam_size", 1),
                "best_of": self.config.get("whisper_best_of", 1),
            }
            language = self.config.get("whisper_language", "auto")
            if language and language != "auto":
                kwargs["language"] = language

            subtitles = self.transcriber.transcribe_to_subtitles(
                preview_wav,
                model_name=self.config.get("whisper_model", "base"),
                device=self.config.get("device", "auto"),
                **kwargs,
            )
        except Exception:
            return ""
        finally:
            try:
                Path(preview_wav).unlink(missing_ok=True)
            except Exception:
                pass

        parts: list[str] = []
        for subtitle in subtitles:
            text = subtitle.text.strip()
            if len(text) < 6:
                continue
            parts.append(text)
            if len(" ".join(parts)) >= 80 or len(parts) >= 3:
                break
        return " ".join(parts).strip()

    def _get_audio_duration_seconds(self, audio_path: str) -> float:
        try:
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                audio_path,
            ]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            if proc.returncode != 0:
                return 0.0
            return float(proc.stdout.strip() or 0.0)
        except Exception:
            return 0.0

    def _build_sample_offsets(self, duration: float, seconds: int) -> list[int]:
        if duration <= 0:
            return [0, 24, 48]

        max_start = max(int(duration) - seconds, 0)
        candidates = [
            0,
            max(int(duration * 0.25) - seconds // 2, 0),
            max(int(duration * 0.55) - seconds // 2, 0),
            max(int(duration * 0.8) - seconds // 2, 0),
        ]

        offsets: list[int] = []
        for candidate in candidates:
            clamped = min(max(candidate, 0), max_start)
            if clamped not in offsets:
                offsets.append(clamped)
        return offsets

    def _make_preview_wav(self, audio_path: str, start_seconds: int, seconds: int) -> Optional[str]:
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
                str(start_seconds),
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

    def _refresh_playlist_names(self) -> None:
        for index, path in enumerate(self.player.playlist):
            row = self.playlist.topLevelItem(index)
            if row is None:
                continue
            row.setText(0, str(index + 1))
            row.setData(0, Qt.UserRole, path)
            row.setText(1, Path(path).name)

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
        index = self.player.current_index - 1 if self.player.current_index > 0 else len(self.player.playlist) - 1
        self._play_index(index)

    def _next(self) -> None:
        if self._closing_ui or self._loading_folder:
            return
        if not self.player.playlist:
            return
        index = self.player.current_index + 1 if self.player.current_index < len(self.player.playlist) - 1 else 0
        self._play_index(index)

    def _play_index(self, index: int) -> None:
        if self._closing_ui or self._loading_folder:
            return
        if not (0 <= index < len(self.player.playlist)):
            return

        self.transcription_manager.cancel_active()

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
        self._refresh_row_state(path, subtitles="Ready" if self.player.current_subtitles else "Missing", task="Idle")

    def _tick(self) -> None:
        if self._closing_ui or self._loading_folder:
            return

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

        self.transcription_manager.tick()

    def _on_subtitle_needed(self, audio_path: str) -> None:
        self.transcription_manager.start_for_path(audio_path)

    def _on_transcription_started(self, path: str) -> None:
        self._refresh_row_state(path, task="Run")
        if self.player.current_file == path and not self._status_active:
            status = "Generating subtitles..."
            self._append_subtitle_line(status, self._fmt_status)
            self._last_status_text = status
            self._status_active = True

    def _on_transcription_ready(self, path: str, model: str) -> None:
        task = model.capitalize()
        self._refresh_row_state(path, subtitles="Ready", task=task)

    def _on_transcription_failed(self, path: str, model: str, error: str) -> None:
        self._refresh_row_state(path, task="Fail")
        self.log.append(f"[{model}] Transcription failed: {error}")

    def _refresh_row_state(
        self,
        path: str,
        subtitles: Optional[str] = None,
        task: Optional[str] = None,
    ) -> None:
        for index in range(self.playlist.topLevelItemCount()):
            row = self.playlist.topLevelItem(index)
            if row and row.data(0, Qt.UserRole) == path:
                if subtitles is not None:
                    row.setText(3, subtitles)
                if task is not None:
                    row.setText(4, task)
                break

    def _append_log(self, message: str) -> None:
        self.log.append(message)

    def _on_subtitle_changed(self, subtitle: Optional[Subtitle]) -> None:
        self.subtitle_signal.emit(subtitle)

    def _apply_subtitle(self, subtitle_obj: object) -> None:
        subtitle = subtitle_obj if isinstance(subtitle_obj, Subtitle) else None
        if subtitle is None:
            current_path = self.player.current_file
            if current_path and self.transcription_manager.is_transcribing(current_path):
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

        self.transcription_manager.shutdown()
        self.player.cleanup()
        super().closeEvent(event)

    def run(self) -> None:
        self.show()
        self._app.exec()
