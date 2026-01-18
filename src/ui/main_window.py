"""
主視窗模組
整合所有 UI 組件並管理應用程式主視窗
"""

import tkinter as tk
import os
from tkinter import filedialog, scrolledtext
from typing import Optional

from src.core.audio_player import AudioPlayer
from src.core.transcriber import Transcriber
from src.utils.file_utils import find_audio_files, has_srt_file
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
        
        # 初始化核心組件
        self.player = AudioPlayer()
        self.transcriber = Transcriber()
        
        # 設置播放器回調
        self.player.on_subtitle_changed = self._on_subtitle_changed
        self.player.on_position_changed = self._on_position_changed
        self.player.on_playback_end = self._on_playback_end
        self.player.on_subtitle_needed = self._on_subtitle_needed
        
        # 轉錄狀態追蹤
        self._transcribing_files = set()  # 正在轉錄的檔案集合
        
        # 創建 UI 組件
        self._create_ui()
        
        # 綁定關閉事件
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
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
        self.progress_bar.pack(pady=10)
        
        # 播放列表
        self.playlist_view = PlaylistView(self.root, width=50, height=20)
        self.playlist_view.on_item_select = self._on_playlist_select
        self.playlist_view.pack(pady=10)
    
    def _on_play_directory(self) -> None:
        """處理播放目錄事件"""
        directory_path = filedialog.askdirectory(title="選擇音頻目錄")
        if not directory_path:
            return
        
        # 查找音頻檔案
        audio_files = find_audio_files(directory_path)
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
            file_path = self.player.playlist[index]
            self.player.current_index = index
            self._play_with_subtitle_check(file_path)
            self.playlist_view.set_current_index(index)
    
    def _on_subtitle_changed(self, subtitle: Optional) -> None:
        """處理字幕變更事件"""
        self.root.after(0, lambda: self.subtitle_display.update_subtitle(subtitle))
    
    def _on_position_changed(self, position: float) -> None:
        """處理播放位置變更事件"""
        self.root.after(0, lambda: self.progress_bar.set_value(position))
    
    def _on_playback_end(self) -> None:
        """處理播放結束事件"""
        # 自動播放下一首
        if self.player.playlist:
            self.root.after(0, self._auto_play_next)
    
    def _play_with_subtitle_check(self, audio_path: str) -> None:
        """
        播放音頻檔案，如果沒有字幕則先等待轉錄完成
        
        Args:
            audio_path: 音頻檔案路徑
        """
        # 檢查是否有字幕
        if has_srt_file(audio_path):
            # 有字幕，直接播放
            self.player.play(audio_path)
            self.progress_bar.set_maximum(self.player.current_duration)
            # 更新播放按鈕狀態（播放中應顯示暫停圖標）
            self.controls.update_pause_button(self.player.is_paused)
        else:
            # 沒有字幕，先轉錄再播放
            auto_transcribe = self.config.get("auto_transcribe_on_play", True)
            if auto_transcribe:
                # 顯示轉錄提示
                self.subtitle_display.update_subtitle(None)
                filename = os.path.basename(audio_path)
                self._log_message(f"缺少字幕，正在轉錄: {filename}...")
                self.root.update()  # 更新 UI 以顯示訊息
                
                # 同步轉錄（等待完成）
                try:
                    srt_path = self.transcriber.transcribe_to_srt(
                        audio_path,
                        model_name=self.config.get("whisper_model", "base"),
                        device=self.config.get("device", "auto")
                    )
                    self._log_message(f"✓ 轉錄完成: {filename}")
                    
                    # 轉錄完成後再播放
                    self.player.play(audio_path)
                    self.progress_bar.set_maximum(self.player.current_duration)
                    self.playlist_view._update_display()  # 更新列表顯示
                    # 更新播放按鈕狀態（播放中應顯示暫停圖標）
                    self.controls.update_pause_button(self.player.is_paused)
                except Exception as e:
                    self._log_message(f"✗ 轉錄失敗: {filename} - {str(e)}")
                    # 即使轉錄失敗也播放（無字幕）
                    self.player.play(audio_path)
                    self.progress_bar.set_maximum(self.player.current_duration)
                    # 更新播放按鈕狀態（播放中應顯示暫停圖標）
                    self.controls.update_pause_button(self.player.is_paused)
            else:
                # 未啟用自動轉錄，直接播放（無字幕）
                self._log_message(f"未啟用自動轉錄，直接播放: {os.path.basename(audio_path)}")
                self.player.play(audio_path)
                self.progress_bar.set_maximum(self.player.current_duration)
                # 更新播放按鈕狀態（播放中應顯示暫停圖標）
                self.controls.update_pause_button(self.player.is_paused)
    
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
    
    def _on_subtitle_needed(self, audio_path: str) -> None:
        """
        處理需要轉錄字幕的情況（當播放沒有字幕的檔案時自動觸發）
        
        Args:
            audio_path: 需要轉錄的音頻檔案路徑
        """
        # 檢查配置是否啟用自動轉錄
        auto_transcribe = self.config.get("auto_transcribe_on_play", True)
        if not auto_transcribe:
            self._log_message(f"未啟用自動轉錄: {os.path.basename(audio_path)}")
            return
        
        # 避免重複轉錄同一個檔案
        if audio_path in self._transcribing_files:
            return
        
        # 顯示轉錄提示
        self.root.after(0, lambda: self.subtitle_display.update_subtitle(None))
        self._log_message(f"檢測到缺少字幕，開始轉錄: {os.path.basename(audio_path)}")
        
        # 標記為正在轉錄
        self._transcribing_files.add(audio_path)
        
        # 啟動背景轉錄（不阻塞播放）
        import threading
        threading.Thread(
            target=self._transcribe_current_file,
            args=(audio_path,),
            daemon=True
        ).start()
    
    def _transcribe_current_file(self, audio_path: str) -> None:
        """
        轉錄當前播放的檔案
        
        Args:
            audio_path: 音頻檔案路徑
        """
        try:
            srt_path = self.transcriber.transcribe_to_srt(
                audio_path,
                model_name=self.config.get("whisper_model", "base"),
                device=self.config.get("device", "auto")
            )
            
            # 轉錄完成，更新 UI 並重新載入字幕
            self.root.after(0, self._on_transcription_complete, audio_path)
            
        except Exception as e:
            # 轉錄失敗
            self.root.after(0, self._on_transcription_failed, audio_path, str(e))
        finally:
            # 移除轉錄標記
            self._transcribing_files.discard(audio_path)
    
    def _on_transcription_complete(self, audio_path: str) -> None:
        """轉錄完成後的處理"""
        # 記錄成功訊息
        self._log_message(f"✓ 轉錄完成: {os.path.basename(audio_path)}")
        
        # 如果這是當前播放的檔案，重新載入字幕
        if self.player.current_file == audio_path:
            if self.player.reload_subtitles(audio_path):
                self._log_message("字幕已載入並開始顯示")
                # 更新播放列表顯示（加粗標記有字幕的檔案）
                self.playlist_view._update_display()
            else:
                self._log_message("警告: 字幕檔案已生成但載入失敗")
    
    def _on_transcription_failed(self, audio_path: str, error: str) -> None:
        """轉錄失敗後的處理"""
        self._log_message(f"✗ 轉錄失敗: {os.path.basename(audio_path)} - {error}")
    
    def _transcribe_playlist_background(self, audio_files: list) -> None:
        """背景轉錄播放列表中的音頻"""
        import threading
        
        def transcribe():
            for file_path in audio_files:
                srt_path = self.transcriber.transcribe_to_srt(
                    file_path,
                    model_name=self.config.get("whisper_model", "base"),
                    device=self.config.get("device", "auto")
                )
                self._log_message(f"已轉錄: {os.path.basename(file_path)}")
                # 更新播放列表顯示
                self.root.after(0, self.playlist_view._update_display)
        
        threading.Thread(target=transcribe, daemon=True).start()
    
    def _log_message(self, message: str) -> None:
        """記錄訊息"""
        self.conversion_messages.insert(tk.END, message + "\n")
        self.conversion_messages.see(tk.END)
    
    def _on_close(self) -> None:
        """處理關閉事件"""
        self.player.cleanup()
        self.root.destroy()
    
    def run(self) -> None:
        """運行應用程式"""
        self.root.mainloop()
