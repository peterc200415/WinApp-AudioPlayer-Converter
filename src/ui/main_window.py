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
        
        # 初始化核心組件
        self.player = AudioPlayer()
        self.transcriber = Transcriber()
        
        # 設置播放器回調
        self.player.on_subtitle_changed = self._on_subtitle_changed
        self.player.on_position_changed = self._on_position_changed
        self.player.on_playback_end = self._on_playback_end
        
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
        
        # 開始播放第一首
        if audio_files:
            self.player.current_index = 0
            self.player.play(audio_files[0])
            self.playlist_view.set_current_index(0)
            
            # 背景轉錄（如果需要）
            if self.config.get("auto_transcribe", False):
                self._transcribe_playlist_background(audio_files)
    
    def _on_pause(self) -> None:
        """處理暫停事件"""
        self.player.toggle_pause()
        self.controls.update_pause_button(self.player.is_paused)
    
    def _on_next(self) -> None:
        """處理下一首事件"""
        if self.player.next_track():
            self.playlist_view.set_current_index(self.player.current_index)
    
    def _on_previous(self) -> None:
        """處理上一首事件"""
        if self.player.previous_track():
            self.playlist_view.set_current_index(self.player.current_index)
    
    def _on_playlist_select(self, index: int) -> None:
        """處理播放列表選擇事件"""
        if self.player.play_index(index):
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
    
    def _auto_play_next(self) -> None:
        """自動播放下一首"""
        if self.player.next_track():
            self.playlist_view.set_current_index(self.player.current_index)
            self.progress_bar.set_maximum(self.player.current_duration)
    
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
