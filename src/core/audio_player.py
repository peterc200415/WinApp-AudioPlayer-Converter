"""
音頻播放器核心模組
提供音頻播放的核心功能
"""

import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

import pygame


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

from pydub import AudioSegment

from src.core.subtitle_parser import SubtitleParser, Subtitle
from src.utils.file_utils import get_srt_file_path, has_srt_file


class AudioPlayer:
    """音頻播放器核心類"""
    
    # 支持的音頻格式
    SUPPORTED_FORMATS = ('.mp3', '.m4a', '.wav', '.wma')
    
    def __init__(self):
        """初始化播放器"""
        pygame.mixer.init()
        self.current_file: Optional[str] = None
        self.playlist: List[str] = []
        self.current_index: int = -1
        self.current_duration: float = 0.0
        self.current_subtitles: List[Subtitle] = []
        self._subtitle_cache: Dict[str, List[Subtitle]] = {}
        
        self.is_playing: bool = False
        self.is_paused: bool = False
        self.is_closing: bool = False
        self.volume: float = 1.0  # 音量範圍 0.0 - 1.0
        
        self.temp_files: List[str] = []  # 追蹤臨時檔案
        
        # 回調函數
        self.on_position_changed: Optional[Callable[[float], None]] = None
        self.on_subtitle_changed: Optional[Callable[[Optional[Subtitle]], None]] = None
        self.on_playback_end: Optional[Callable[[], None]] = None
        self.on_subtitle_needed: Optional[Callable[[str], None]] = None  # 當需要轉錄字幕時觸發
        
        # 背景執行緒
        self._subtitle_thread: Optional[threading.Thread] = None
        self._progress_thread: Optional[threading.Thread] = None

        # 字幕更新去重（避免 UI 在沒有字幕時一直被刷新）
        self._last_subtitle_valid: bool = False
        self._last_subtitle: Optional[Subtitle] = None

    def has_subtitles(self, audio_path: str) -> bool:
        """檢查是否已具備字幕（記憶體快取或磁碟 SRT）。"""
        if audio_path in self._subtitle_cache:
            return True
        return has_srt_file(audio_path)

    def set_cached_subtitles(self, audio_path: str, subtitles: List[Subtitle]) -> None:
        """將字幕寫入記憶體快取，必要時更新目前顯示的字幕。"""
        self._subtitle_cache[audio_path] = subtitles
        if self.current_file == audio_path:
            self.current_subtitles = subtitles
            # 讓下一次字幕更新強制通知 UI
            self._last_subtitle_valid = False
    
    def load_file(self, file_path: str) -> bool:
        """
        載入音頻檔案
        
        Args:
            file_path: 音頻檔案路徑
        
        Returns:
            是否成功載入
        """
        if not os.path.exists(file_path):
            print(f"檔案不存在: {file_path}")
            return False
        
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in self.SUPPORTED_FORMATS:
            print(f"不支持的音頻格式: {file_ext}")
            return False
        
        self.current_file = file_path
        
        # 載入字幕（優先使用記憶體快取，其次讀取磁碟 SRT）
        try:
            if file_path in self._subtitle_cache:
                self.current_subtitles = self._subtitle_cache[file_path]
            else:
                srt_path = get_srt_file_path(file_path)
                if os.path.exists(srt_path):
                    self.current_subtitles = SubtitleParser.parse_srt(srt_path)
                else:
                    self.current_subtitles = []
        except Exception as e:
            print(f"載入字幕失敗: {e}")
            self.current_subtitles = []
        
        # 獲取音頻時長
        try:
            audio = AudioSegment.from_file(file_path)
            self.current_duration = len(audio) / 1000.0  # 轉換為秒
        except Exception as e:
            print(f"獲取音頻時長失敗: {e}")
            self.current_duration = 0.0
        
        return True
    
    def reload_subtitles(self, file_path: Optional[str] = None) -> bool:
        """
        重新載入字幕檔案（用於轉錄完成後）
        
        Args:
            file_path: 音頻檔案路徑，如果為 None 則使用當前檔案
        
        Returns:
            是否成功載入
        """
        if file_path is None:
            file_path = self.current_file
        
        if not file_path:
            return False
        
        srt_path = get_srt_file_path(file_path)
        try:
            if os.path.exists(srt_path):
                self.current_subtitles = SubtitleParser.parse_srt(srt_path)
                return True
            else:
                self.current_subtitles = []
                return False
        except Exception as e:
            print(f"重新載入字幕失敗: {e}")
            self.current_subtitles = []
            return False
    
    def play(self, file_path: Optional[str] = None) -> bool:
        """
        播放音頻
        
        Args:
            file_path: 音頻檔案路徑，如果為 None 則播放當前檔案
        
        Returns:
            是否成功播放
        """
        if file_path:
            if not self.load_file(file_path):
                return False

        # 某些流程（例如視窗關閉後重開）可能讓 mixer 未初始化
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except Exception as e:
            print(f"初始化音頻設備失敗: {e}")
            return False
        
        if not self.current_file:
            print("沒有載入的音頻檔案")
            return False
        
        # 停止當前播放
        self.stop()

        # 重置字幕通知狀態（新曲目開始時，至少通知 UI 一次）
        self._last_subtitle_valid = False
        
        file_ext = Path(self.current_file).suffix.lower()
        
        try:
            if file_ext == '.mp3' or file_ext == '.wav':
                pygame.mixer.music.load(self.current_file)
                pygame.mixer.music.set_volume(self.volume)  # 設置音量
                pygame.mixer.music.play()
            elif file_ext == '.m4a':
                if not self._convert_and_play_m4a():
                    return False
            elif file_ext == '.wma':
                if not self._convert_and_play_wma():
                    return False
            else:
                print(f"不支持的格式: {file_ext}")
                return False
            
            self.is_playing = True
            self.is_paused = False

            # 啟動字幕和進度更新執行緒
            self._start_subtitle_thread()
            self._start_progress_thread()

            # 若沒有字幕，觸發背景轉錄（由 UI 決定是否執行與如何排程）
            if not self.current_subtitles and self.current_file and self.on_subtitle_needed:
                self.on_subtitle_needed(self.current_file)
            
            return True
        except Exception as e:
            print(f"播放失敗: {e}")
            return False
    
    def _convert_and_play_m4a(self) -> bool:
        """將 M4A 轉換為 WAV 並播放"""
        try:
            audio = AudioSegment.from_file(self.current_file)
            temp_wav_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_wav_file.close()
            audio.export(temp_wav_file.name, format="wav")
            self.temp_files.append(temp_wav_file.name)
            
            pygame.mixer.music.load(temp_wav_file.name)
            pygame.mixer.music.set_volume(self.volume)  # 設置音量
            pygame.mixer.music.play()
            return True
        except Exception as e:
            print(f"M4A 轉換失敗: {e}")
            return False
    
    def _convert_and_play_wma(self) -> bool:
        """將 WMA 轉換為 WAV 並播放"""
        try:
            audio = AudioSegment.from_file(self.current_file)
            temp_wav_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_wav_file.close()
            audio.export(temp_wav_file.name, format="wav")
            self.temp_files.append(temp_wav_file.name)
            
            pygame.mixer.music.load(temp_wav_file.name)
            pygame.mixer.music.set_volume(self.volume)  # 設置音量
            pygame.mixer.music.play()
            return True
        except Exception as e:
            print(f"WMA 轉換失敗: {e}")
            return False
    
    def pause(self) -> None:
        """暫停播放"""
        if self.is_playing and not self.is_paused:
            pygame.mixer.music.pause()
            self.is_paused = True
    
    def unpause(self) -> None:
        """恢復播放"""
        if self.is_playing and self.is_paused:
            pygame.mixer.music.unpause()
            self.is_paused = False
    
    def toggle_pause(self) -> None:
        """切換暫停狀態"""
        if self.is_paused:
            self.unpause()
        else:
            self.pause()
    
    def stop(self) -> None:
        """停止播放"""
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass
        self.is_playing = False
        self.is_paused = False
        
        # 停止背景執行緒
        if self._subtitle_thread and self._subtitle_thread.is_alive():
            # 執行緒會自動檢測 is_closing
            pass
        
        # 清理臨時檔案
        self._cleanup_temp_files()
    
    def get_position(self) -> float:
        """
        獲取當前播放位置（秒）
        
        Returns:
            當前播放位置
        """
        if not self.is_playing:
            return 0.0
        pos = pygame.mixer.music.get_pos()
        return pos / 1000.0 if pos > 0 else 0.0
    
    def set_volume(self, volume: float) -> None:
        """
        設置音量
        
        Args:
            volume: 音量值（0.0 - 1.0）
        """
        self.volume = max(0.0, min(1.0, volume))  # 限制在 0.0-1.0 範圍
        pygame.mixer.music.set_volume(self.volume)
    
    def get_volume(self) -> float:
        """
        獲取當前音量
        
        Returns:
            當前音量值（0.0 - 1.0）
        """
        return self.volume
    
    def set_playlist(self, file_list: List[str]) -> None:
        """
        設置播放列表
        
        Args:
            file_list: 音頻檔案路徑列表
        """
        self.playlist = [f for f in file_list if Path(f).suffix.lower() in self.SUPPORTED_FORMATS]
    
    def next_track(self) -> bool:
        """
        播放下一首
        
        Returns:
            是否成功播放
        """
        if not self.playlist:
            return False
        
        if self.current_index < len(self.playlist) - 1:
            self.current_index += 1
        else:
            self.current_index = 0  # 循環播放
        
        return self.play(self.playlist[self.current_index])
    
    def previous_track(self) -> bool:
        """
        播放上一首
        
        Returns:
            是否成功播放
        """
        if not self.playlist:
            return False
        
        if self.current_index > 0:
            self.current_index -= 1
        else:
            self.current_index = len(self.playlist) - 1  # 循環播放
        
        return self.play(self.playlist[self.current_index])
    
    def play_index(self, index: int) -> bool:
        """
        播放指定索引的音頻
        
        Args:
            index: 播放列表索引
        
        Returns:
            是否成功播放
        """
        if 0 <= index < len(self.playlist):
            self.current_index = index
            return self.play(self.playlist[index])
        return False
    
    def _start_subtitle_thread(self) -> None:
        """啟動字幕更新執行緒"""
        if self._subtitle_thread and self._subtitle_thread.is_alive():
            return
        
        self._subtitle_thread = threading.Thread(target=self._update_subtitles, daemon=True)
        self._subtitle_thread.start()
    
    def _start_progress_thread(self) -> None:
        """啟動進度更新執行緒"""
        if self._progress_thread and self._progress_thread.is_alive():
            return
        
        self._progress_thread = threading.Thread(target=self._update_progress, daemon=True)
        self._progress_thread.start()
    
    def _update_subtitles(self) -> None:
        """更新字幕（背景執行緒）"""
        while self.is_playing and not self.is_closing:
            if not self.is_paused:
                current_time = self.get_position()
                subtitle = SubtitleParser.find_subtitle_by_time(self.current_subtitles, current_time)

                if self.on_subtitle_changed:
                    if (not self._last_subtitle_valid) or (subtitle != self._last_subtitle):
                        self._last_subtitle = subtitle
                        self._last_subtitle_valid = True
                        self.on_subtitle_changed(subtitle)
            
            time.sleep(0.5)
    
    def _update_progress(self) -> None:
        """更新播放進度（背景執行緒）"""
        not_busy_ticks = 0
        loop_started_at = time.time()
        while self.is_playing and not self.is_closing:
            position = self.get_position()
            if not self.is_paused:
                if self.on_position_changed:
                    self.on_position_changed(position)
            
            # 檢查播放是否結束
            if self.is_playing and not self.is_paused:
                is_busy = pygame.mixer.music.get_busy()
                if is_busy:
                    not_busy_ticks = 0
                else:
                    # 某些格式/裝置在啟動初期會短暫回報 not busy，避免誤判播放結束
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
        """清理臨時檔案"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    # 嘗試多次刪除
                    for _ in range(3):
                        try:
                            os.remove(temp_file)
                            break
                        except PermissionError:
                            time.sleep(0.1)
            except Exception as e:
                print(f"清理臨時檔案失敗: {temp_file}, {e}")
        
        self.temp_files.clear()
    
    def cleanup(self) -> None:
        """清理資源"""
        self.is_closing = True
        self.stop()
        self._cleanup_temp_files()
        pygame.mixer.quit()
