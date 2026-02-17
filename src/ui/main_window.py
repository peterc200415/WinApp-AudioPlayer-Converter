"""
主視窗模組
整合所有 UI 組件並管理應用程式主視窗
"""

import os
import queue
import threading
import tempfile
import subprocess
import tkinter as tk
from tkinter import filedialog, scrolledtext
from typing import Optional

from src.core.audio_player import AudioPlayer
from src.core.subtitle_parser import Subtitle
from src.core.transcriber import Transcriber
from src.utils.file_utils import find_audio_files
from src.utils.config import Config
from src.ui.components.subtitle_display import SubtitleDisplay
from src.ui.components.playlist_view import PlaylistView
from src.ui.components.player_controls import PlayerControls
from src.ui.components.progress_bar import ProgressBar


class MainWindow:
    """主視窗類"""
    
    def __init__(self):
        """初始化主視窗"""
        # 載入配置
        self.config = Config()
        
        # 創建 Tkinter 根視窗
        self.root = tk.Tk()
        self.root.title("Peter Audio Player")
        self._ensure_window_visible()
        
        # 初始化核心組件
        self.player = AudioPlayer()
        self.transcriber = Transcriber()
        
        # 設置播放器回調
        self.player.on_subtitle_changed = self._on_subtitle_changed
        self.player.on_position_changed = self._on_position_changed
        self.player.on_playback_end = self._on_playback_end
        self.player.on_subtitle_needed = self._on_subtitle_needed
        
        # 轉錄狀態追蹤
        self._transcribing_files = set()  # 正在產生字幕的檔案集合（滾動式 chunk 模式）
        self._preview_next_start: dict[str, float] = {}
        self._preview_inflight: set[tuple[str, int]] = set()
        self._scheduler_job: Optional[str] = None

        # 背景轉錄佇列（單一 worker，避免同時多個 Whisper 任務）
        self._transcribing_lock = threading.Lock()
        self._transcribe_queue: "queue.Queue[Optional[dict]]" = queue.Queue()
        self._transcribe_stop = threading.Event()
        self._transcribe_worker_thread = threading.Thread(
            target=self._transcription_worker,
            daemon=True,
        )
        self._transcribe_worker_thread.start()

        # 週期性排程：需要時生成下一段字幕 chunk
        self._start_subtitle_scheduler()
        
        # 創建 UI 組件
        self._create_ui()
        
        # 綁定關閉事件
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _ensure_window_visible(self) -> None:
        """Best-effort: ensure the Tk window is on-screen and frontmost."""
        try:
            self.root.update_idletasks()

            # Give a reasonable default size and center it
            req_w = max(700, self.root.winfo_reqwidth())
            req_h = max(700, self.root.winfo_reqheight())
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            x = max(0, (screen_w - req_w) // 2)
            y = max(0, (screen_h - req_h) // 3)
            self.root.geometry(f"{req_w}x{req_h}+{x}+{y}")
            self.root.minsize(600, 500)

            # Deiconify + bring to front
            self.root.wm_state("normal")
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()

            # Temporary topmost to steal focus on Windows
            try:
                self.root.attributes("-topmost", True)
                self.root.after(250, lambda: self.root.attributes("-topmost", False))
            except Exception:
                pass
        except Exception:
            # Never fail app startup due to focus/geometry issues
            pass
    
    def _create_ui(self) -> None:
        """創建用戶界面"""
        # 字幕顯示區域
        self.subtitle_display = SubtitleDisplay(
            self.root,
            font_size=self.config.get("subtitle_font_size", 14),
            width=40,
            height=5
        )
        self.subtitle_display.pack(pady=10)
        
        # 轉錄訊息區域（可選，用於顯示轉錄進度）
        self.conversion_messages = scrolledtext.ScrolledText(
            self.root,
            width=40,
            height=5,
            font=10
        )
        self.conversion_messages.pack(pady=10)
        
        # 播放控制
        self.controls = PlayerControls(self.root)
        self.controls.on_play_directory = self._on_play_directory
        self.controls.on_pause = self._on_pause
        self.controls.on_next = self._on_next
        self.controls.on_previous = self._on_previous
        self.controls.on_close = self._on_close
        self.controls.on_volume_changed = self._on_volume_changed
        self.controls.pack(pady=10)
        
        # 進度條
        self.progress_bar = ProgressBar(self.root, length=400)
        self.progress_bar.on_seek = self._on_progress_seek  # 設置跳轉回調
        self.progress_bar.pack(pady=10)
        
        # 播放列表
        self.playlist_view = PlaylistView(self.root, width=50, height=20)
        self.playlist_view.has_subtitle_func = self.player.has_subtitles
        self.playlist_view.on_item_select = self._on_playlist_select
        self.playlist_view.pack(pady=10)

    def _start_subtitle_scheduler(self) -> None:
        if self._scheduler_job is not None:
            return

        def tick():
            try:
                self._tick_subtitle_scheduler()
            finally:
                self._scheduler_job = self.root.after(500, tick)

        self._scheduler_job = self.root.after(500, tick)

    def _tick_subtitle_scheduler(self) -> None:
        """While playing, keep generating subtitle chunks ahead of playback."""
        if not self.player.is_playing or self.player.is_paused:
            return

        audio_path = self.player.current_file
        if not audio_path:
            return

        if not self.config.get("auto_transcribe_on_play", True):
            return

        if not self.config.get("enable_subtitle_preview", True):
            return

        with self._transcribing_lock:
            if audio_path not in self._transcribing_files:
                return

        position = self.player.get_position()
        lead = float(self.config.get("subtitle_chunk_lead_seconds", 8))
        chunk_seconds = int(self.config.get("subtitle_preview_seconds", 45))
        if chunk_seconds <= 0:
            return

        next_start = float(self._preview_next_start.get(audio_path, 0.0))
        # If we already have subtitles, advance next_start to the end of cached subtitles
        if self.player.current_subtitles:
            try:
                last_end = max(s.end_time for s in self.player.current_subtitles)
                if last_end > next_start:
                    next_start = last_end
                    self._preview_next_start[audio_path] = next_start
            except Exception:
                pass

        if self.player.current_duration and next_start >= (self.player.current_duration + 0.5):
            return

        # Enqueue next chunk when close to next_start
        if position + lead >= next_start:
            self._enqueue_preview_chunk(audio_path, start_seconds=int(next_start), seconds=chunk_seconds)
    
    def _on_play_directory(self) -> None:
        """處理播放目錄事件"""
        directory_path = filedialog.askdirectory(title="選擇音頻目錄")
        if not directory_path:
            return
        
        # 查找音頻檔案（使用配置中支援的格式）
        supported_formats = self.config.get("supported_formats", [".mp3", ".m4a", ".wav", ".wma"])
        audio_files = find_audio_files(directory_path, extensions=supported_formats)
        if not audio_files:
            self._log_message("目錄中沒有找到音頻檔案")
            return
        
        # 設置播放列表
        self.player.set_playlist(audio_files)
        self.playlist_view.set_playlist(audio_files)
        
        # 設置當前索引為第一首（但不自動播放，等待用戶按下播放按鈕）
        if audio_files:
            self.player.current_index = 0
            self.playlist_view.set_current_index(0)
            self._log_message(f"已載入 {len(audio_files)} 個音頻檔案，請點擊播放按鈕開始播放")
            
            # 背景轉錄（如果需要）
            if self.config.get("auto_transcribe", False):
                self._transcribe_playlist_background(audio_files)
    
    def _on_pause(self) -> None:
        """處理暫停/播放事件"""
        if not self.player.is_playing and not self.player.is_paused:
            # 如果沒有播放也沒有暫停，表示尚未開始播放，則開始播放當前索引的檔案
            if self.player.playlist and 0 <= self.player.current_index < len(self.player.playlist):
                file_path = self.player.playlist[self.player.current_index]
                self._play_with_subtitle_check(file_path)
                self.playlist_view.set_current_index(self.player.current_index)
            else:
                # 如果沒有播放列表，提示用戶
                self._log_message("請先選擇音頻目錄")
        else:
            # 如果正在播放或暫停，則切換暫停狀態
            self.player.toggle_pause()
        self.controls.update_pause_button(self.player.is_paused)
    
    def _on_volume_changed(self, volume: float) -> None:
        """處理音量變更事件"""
        self.player.set_volume(volume)
    
    def _on_next(self) -> None:
        """處理下一首事件"""
        if self.player.playlist:
            # 停止当前歌曲的转码
            self._cancel_current_transcription()
            
            if self.player.current_index < len(self.player.playlist) - 1:
                next_index = self.player.current_index + 1
            else:
                next_index = 0
            
            if 0 <= next_index < len(self.player.playlist):
                file_path = self.player.playlist[next_index]
                self.player.current_index = next_index
                self._play_with_subtitle_check(file_path)
                self.playlist_view.set_current_index(next_index)
    
    def _on_previous(self) -> None:
        """處理上一首事件"""
        if self.player.playlist:
            # 停止当前歌曲的转码
            self._cancel_current_transcription()
            
            if self.player.current_index > 0:
                prev_index = self.player.current_index - 1
            else:
                prev_index = len(self.player.playlist) - 1
            
            if 0 <= prev_index < len(self.player.playlist):
                file_path = self.player.playlist[prev_index]
                self.player.current_index = prev_index
                self._play_with_subtitle_check(file_path)
                self.playlist_view.set_current_index(prev_index)
    
    def _on_playlist_select(self, index: int) -> None:
        """處理播放列表選擇事件"""
        if 0 <= index < len(self.player.playlist):
            # 停止当前歌曲的转码
            self._cancel_current_transcription()
            
            file_path = self.player.playlist[index]
            self.player.current_index = index
            self._play_with_subtitle_check(file_path)
            self.playlist_view.set_current_index(index)
    
    def _on_subtitle_changed(self, subtitle: Optional[Subtitle]) -> None:
        """處理字幕變更事件"""
        def update():
            if subtitle is None:
                current = self.player.current_file
                if current and self._is_transcribing(current):
                    # When we have a gap (e.g. chunk not ready yet), show an explicit status
                    self.subtitle_display.show_status("字幕生成中...")
                    return
                self.subtitle_display.clear()
                return

            # Show single line (current subtitle)
            self.subtitle_display.update_subtitle(subtitle)

        self.root.after(0, update)
    
    def _on_position_changed(self, position: float) -> None:
        """處理播放位置變更事件"""
        self.root.after(0, lambda: self.progress_bar.set_value(position))
    
    def _on_progress_seek(self, target_time: float) -> None:
        """
        處理進度條跳轉事件
        
        Args:
            target_time: 目標時間（秒）
        """
        # 注意：pygame.mixer.music 不支持直接跳轉，此功能需要重新載入音頻
        # 這裡只記錄訊息，實際跳轉功能可以通過重新播放實現（稍後可優化）
        if self.player.is_playing and self.player.current_file:
            # 目前 pygame 不支持跳轉，所以暫時只顯示訊息
            # 未來可以通過 pydub 裁剪音頻並重新播放來實現
            self._log_message(f"跳轉功能：pygame 不支持直接跳轉，目標時間 {int(target_time)}秒", "warning")
    
    def _on_playback_end(self) -> None:
        """處理播放結束事件"""
        # 停止當前檔案的滾動字幕生成
        finished = self.player.current_file
        if finished:
            with self._transcribing_lock:
                self._transcribing_files.discard(finished)
                self._preview_next_start.pop(finished, None)
                # inflight jobs will drain naturally

        # 自動播放下一首
        if self.player.playlist:
            self.root.after(0, self._auto_play_next)
    
    def _play_with_subtitle_check(self, audio_path: str) -> None:
        """
        播放音頻檔案：永遠先播放，字幕背景生成並自動接上
        
        Args:
            audio_path: 音頻檔案路徑
        """
        if not self.player.play(audio_path):
            self._log_message(f"播放失敗: {os.path.basename(audio_path)}", "error")
            return

        self.progress_bar.set_maximum(self.player.current_duration)
        self.controls.update_pause_button(self.player.is_paused)

        # 若目前沒有字幕，顯示狀態（背景轉錄由 AudioPlayer.on_subtitle_needed 觸發）
        if not self.player.current_subtitles:
            if self.config.get("auto_transcribe_on_play", True):
                self.subtitle_display.show_status("字幕轉錄中...")
            else:
                self.subtitle_display.show_status("無字幕")
    
    def _auto_play_next(self) -> None:
        """自動播放下一首"""
        if self.player.playlist:
            if self.player.current_index < len(self.player.playlist) - 1:
                next_index = self.player.current_index + 1
            else:
                next_index = 0
            
            if 0 <= next_index < len(self.player.playlist):
                file_path = self.player.playlist[next_index]
                self.player.current_index = next_index
                self._play_with_subtitle_check(file_path)
                self.playlist_view.set_current_index(next_index)

    def _is_transcribing(self, audio_path: str) -> bool:
        with self._transcribing_lock:
            return audio_path in self._transcribing_files

    def _cancel_current_transcription(self) -> None:
        """取消当前歌曲的转码任务"""
        current = self.player.current_file
        if not current:
            return
        
        with self._transcribing_lock:
            self._transcribing_files.discard(current)
            self._preview_next_start.pop(current, None)
            # 清除与当前文件相关的 inflight 任务
            self._preview_inflight = {
                key for key in self._preview_inflight 
                if key[0] != current
            }
        
        # 清空字幕显示
        self.subtitle_display.clear()

    def _start_rolling_transcription(self, audio_path: str) -> None:
        """Start rolling chunk transcription for fast subtitle availability."""
        # If we already have subtitles that cover the whole track, skip.
        existing: list[Subtitle] = []
        try:
            if self.player.current_file == audio_path:
                existing = list(self.player.current_subtitles)
            else:
                cache = getattr(self.player, "_subtitle_cache", {})
                existing = list(cache.get(audio_path, []))
        except Exception:
            existing = []

        if self.player.current_file == audio_path and existing and self.player.current_duration:
            try:
                last_end = max(s.end_time for s in existing)
                if last_end >= (self.player.current_duration - 1.0):
                    return
            except Exception:
                pass

        with self._transcribing_lock:
            if audio_path in self._transcribing_files:
                return
            self._transcribing_files.add(audio_path)
            try:
                last_end = max(s.end_time for s in existing) if existing else 0.0
            except Exception:
                last_end = 0.0
            self._preview_next_start[audio_path] = float(last_end)

        if self.player.current_file == audio_path:
            self.subtitle_display.show_status("字幕生成中...")

        chunk_seconds = int(self.config.get("subtitle_preview_seconds", 45))
        self._enqueue_preview_chunk(audio_path, start_seconds=int(self._preview_next_start.get(audio_path, 0.0)), seconds=chunk_seconds)

    def _enqueue_preview_chunk(self, audio_path: str, start_seconds: int, seconds: int) -> None:
        if seconds <= 0:
            return

        key = (audio_path, int(start_seconds))
        with self._transcribing_lock:
            if key in self._preview_inflight:
                return
            self._preview_inflight.add(key)

        self._transcribe_queue.put(
            {
                "kind": "preview_chunk",
                "path": audio_path,
                "start": int(start_seconds),
                "seconds": int(seconds),
            }
        )

    def _make_preview_wav(self, audio_path: str, start_seconds: int, seconds: int) -> Optional[str]:
        """Create a short WAV preview for fast subtitle warmup.

        Returns a temp file path, or None if failed.
        """
        if seconds <= 0:
            return None

        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp_path = tmp.name
            tmp.close()

            # Fast cut using ffmpeg; 16kHz mono WAV is what whisper expects.
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
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                return None

            return tmp_path
        except Exception:
            return None
    
    def _on_subtitle_needed(self, audio_path: str) -> None:
        """
        處理需要轉錄字幕的情況（當播放沒有字幕的檔案時自動觸發）
        
        Args:
            audio_path: 需要轉錄的音頻檔案路徑
        """
        # 檢查配置是否啟用自動轉錄
        auto_transcribe = self.config.get("auto_transcribe_on_play", True)
        if not auto_transcribe:
            return

        self._log_message(f"開始背景字幕生成: {os.path.basename(audio_path)}", "info")
        self._start_rolling_transcription(audio_path)

    def _transcription_worker(self) -> None:
        while not self._transcribe_stop.is_set():
            try:
                job = self._transcribe_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if job is None:
                break

            try:
                if not isinstance(job, dict):
                    continue

                if job.get("kind") != "preview_chunk":
                    continue

                audio_path = str(job.get("path", ""))
                start_seconds = int(job.get("start", 0))
                seconds = int(job.get("seconds", 45))
                if not audio_path:
                    continue

                # Skip stale jobs (e.g. user switched track and canceled this file)
                with self._transcribing_lock:
                    if audio_path not in self._transcribing_files:
                        continue

                device_pref = self.config.get("device", "auto")
                language = self.config.get("whisper_language", "auto")
                beam_size = self.config.get("whisper_beam_size", 1)
                best_of = self.config.get("whisper_best_of", 1)

                transcribe_kwargs = {
                    "beam_size": beam_size,
                    "best_of": best_of,
                }
                if language and language != "auto":
                    transcribe_kwargs["language"] = language

                preview_model = self.config.get("subtitle_preview_model", "tiny")
                preview_wav = self._make_preview_wav(audio_path, start_seconds, seconds)
                if not preview_wav:
                    with self._transcribing_lock:
                        self._preview_next_start[audio_path] = max(
                            self._preview_next_start.get(audio_path, 0.0),
                            start_seconds + seconds,
                        )
                    continue

                try:
                    chunk_subs = self.transcriber.transcribe_to_subtitles(
                        preview_wav,
                        model_name=preview_model,
                        device=device_pref,
                        **transcribe_kwargs,
                    )
                finally:
                    try:
                        os.remove(preview_wav)
                    except Exception:
                        pass

                if not chunk_subs:
                    # No speech in this chunk, move window forward to avoid stalls.
                    with self._transcribing_lock:
                        self._preview_next_start[audio_path] = max(
                            self._preview_next_start.get(audio_path, 0.0),
                            start_seconds + seconds,
                        )
                    continue

                # Offset chunk time back to original audio timeline
                offset = float(start_seconds)
                offset_subs: list[Subtitle] = []
                for i, s in enumerate(chunk_subs, start=1):
                    offset_subs.append(
                        Subtitle(
                            index=i,
                            start_time=s.start_time + offset,
                            end_time=s.end_time + offset,
                            text=s.text,
                        )
                    )

                # Merge into existing cached subtitles
                merged = list(self.player.current_subtitles) if self.player.current_file == audio_path else []
                if audio_path in getattr(self.player, "_subtitle_cache", {}):
                    merged = list(getattr(self.player, "_subtitle_cache")[audio_path])

                merged.extend(offset_subs)
                merged.sort(key=lambda x: (x.start_time, x.end_time))

                # Light de-dup
                deduped: list[Subtitle] = []
                last_key = None
                for s in merged:
                    key = (round(s.start_time, 3), round(s.end_time, 3), s.text)
                    if key == last_key:
                        continue
                    deduped.append(s)
                    last_key = key

                self.player.set_cached_subtitles(audio_path, deduped)
                with self._transcribing_lock:
                    self._preview_next_start[audio_path] = max(self._preview_next_start.get(audio_path, 0.0), start_seconds + seconds)
                self.root.after(0, self.playlist_view._update_display)
            except Exception as e:
                try:
                    audio_path = str(job.get("path", "")) if isinstance(job, dict) else ""
                except Exception:
                    audio_path = ""
                if audio_path:
                    self.root.after(0, self._on_transcription_failed, audio_path, str(e))
            finally:
                try:
                    if isinstance(job, dict) and job.get("kind") == "preview_chunk":
                        audio_path = str(job.get("path", ""))
                        start_seconds = int(job.get("start", 0))
                        with self._transcribing_lock:
                            self._preview_inflight.discard((audio_path, int(start_seconds)))
                except Exception:
                    pass
                try:
                    self._transcribe_queue.task_done()
                except Exception:
                    pass
    
    def _on_transcription_complete(self, audio_path: str) -> None:
        """轉錄完成後的處理"""
        self._log_message(f"✓ 轉錄完成: {os.path.basename(audio_path)}", "success")

        # 更新播放列表顯示（快取字幕也視為已具備字幕）
        self.playlist_view._update_display()

        # 若是當前播放曲目，字幕會在下一次更新 tick 自動開始顯示
        if self.player.current_file == audio_path and self.player.current_subtitles:
            self._log_message("字幕已就緒（本次執行期快取）")
    
    def _on_transcription_failed(self, audio_path: str, error: str) -> None:
        """轉錄失敗後的處理"""
        self._log_message(f"✗ 轉錄失敗: {os.path.basename(audio_path)} - {error}", "error")

        if self.player.current_file == audio_path:
            self.subtitle_display.show_status("轉錄失敗，無字幕")
    
    def _transcribe_playlist_background(self, audio_files: list) -> None:
        """背景轉錄播放列表中的音頻"""
        for file_path in audio_files:
            self._start_rolling_transcription(file_path)
    
    def _log_message(self, message: str, message_type: str = "info") -> None:
        """
        記錄訊息（支持顏色分類）
        
        Args:
            message: 訊息內容
            message_type: 訊息類型 ("success", "warning", "error", "info")
        """
        # 定義顏色標籤
        tags = {
            "success": ("success_tag", "#2E7D32"),  # 綠色
            "warning": ("warning_tag", "#F57C00"),  # 橙色
            "error": ("error_tag", "#C62828"),      # 紅色
            "info": ("info_tag", "#1976D2")         # 藍色
        }
        
        # 確保標籤已配置
        tag_name, color = tags.get(message_type, tags["info"])
        if tag_name not in [tag for tag in self.conversion_messages.tag_names()]:
            self.conversion_messages.tag_config(tag_name, foreground=color)
        
        # 插入訊息並應用標籤
        start_pos = self.conversion_messages.index(tk.END)
        self.conversion_messages.insert(tk.END, message + "\n", tag_name)
        self.conversion_messages.see(tk.END)
    
    def _on_close(self) -> None:
        """處理關閉事件"""
        if self._scheduler_job is not None:
            try:
                self.root.after_cancel(self._scheduler_job)
            except Exception:
                pass
            self._scheduler_job = None
        self._transcribe_stop.set()
        try:
            self._transcribe_queue.put_nowait(None)
        except Exception:
            pass
        self.player.cleanup()
        self.root.destroy()
    
    def run(self) -> None:
        """運行應用程式"""
        self.root.mainloop()
