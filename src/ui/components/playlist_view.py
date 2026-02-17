"""
播放列表視圖組件
"""

import tkinter as tk
import os
from typing import List, Optional, Callable

from src.utils.file_utils import has_srt_file


class PlaylistView:
    """播放列表視圖組件類"""
    
    def __init__(self, parent: tk.Widget, width: int = 50, height: int = 20):
        """
        初始化播放列表視圖
        
        Args:
            parent: 父組件
            width: 寬度
            height: 高度
        """
        self.listbox = tk.Text(parent, width=width, height=height, wrap=tk.WORD)
        self.on_item_select: Optional[Callable[[int], None]] = None
        self.has_subtitle_func: Callable[[str], bool] = has_srt_file
        
        # 禁用 Text widget 的默認選擇行為（避免藍色多選）
        self.listbox.config(selectbackground=self.listbox.cget('bg'), 
                           selectforeground=self.listbox.cget('fg'),
                           insertwidth=0)  # 隱藏插入游標
        
        # 配置標籤樣式
        self.listbox.tag_configure('bold', font=('Arial', 10, 'bold'))
        self.listbox.tag_configure('highlight', background='yellow')  # 當前播放項目（黃色）
        self.listbox.tag_configure('hover', background='lightblue')    # 滑鼠懸停（淺藍色）
        
        # 綁定事件
        self.listbox.bind('<Button-1>', self._on_click)
        self.listbox.bind('<Motion>', self._on_motion)  # 滑鼠移動
        self.listbox.bind('<Leave>', self._on_leave)    # 滑鼠離開
        
        self._playlist: List[str] = []
        self._current_index: int = -1
        self._hover_index: Optional[int] = None  # 當前懸停的項目
    
    def pack(self, **kwargs):
        """打包組件"""
        self.listbox.pack(**kwargs)
    
    def grid(self, **kwargs):
        """網格布局"""
        self.listbox.grid(**kwargs)
    
    def set_playlist(self, file_list: List[str]) -> None:
        """
        設置播放列表
        
        Args:
            file_list: 音頻檔案路徑列表
        """
        self._playlist = file_list
        self._update_display()
    
    def set_current_index(self, index: int) -> None:
        """
        設置當前播放項目的索引
        
        Args:
            index: 索引
        """
        self._current_index = index
        self._highlight_current()
    
    def _update_display(self) -> None:
        """更新顯示"""
        # 清除懸停狀態
        self._hover_index = None
        self.listbox.delete(1.0, tk.END)
        
        for i, file_path in enumerate(self._playlist):
            song_name = os.path.basename(file_path)
            
            if self.has_subtitle_func(file_path):
                self.listbox.insert(tk.END, f"{i + 1}. {song_name}\n", 'bold')
            else:
                self.listbox.insert(tk.END, f"{i + 1}. {song_name}\n")
        
        self._highlight_current()
    
    def _highlight_current(self) -> None:
        """高亮當前項目（確保只有一個項目被高亮）"""
        # 清除所有高亮
        self.listbox.tag_remove('highlight', '1.0', tk.END)
        
        # 只高亮當前播放的項目
        if 0 <= self._current_index < len(self._playlist):
            line_num = self._current_index + 1
            start_pos = f'{line_num}.0'
            end_pos = f'{line_num}.end'
            self.listbox.tag_add('highlight', start_pos, end_pos)
    
    def _on_motion(self, event) -> None:
        """處理滑鼠移動事件（懸停效果）"""
        try:
            # 獲取滑鼠位置對應的行號
            index_str = self.listbox.index(f"@{event.x},{event.y}").split('.')[0]
            hover_index = int(index_str) - 1
            
            # 只在有效範圍內且不是當前播放項目時顯示懸停效果
            if 0 <= hover_index < len(self._playlist) and hover_index != self._current_index:
                # 如果懸停的項目改變了，更新顯示
                if hover_index != self._hover_index:
                    # 清除舊的懸停標籤
                    if self._hover_index is not None:
                        old_line = self._hover_index + 1
                        self.listbox.tag_remove('hover', f'{old_line}.0', f'{old_line}.end')
                    
                    # 添加新的懸停標籤
                    self._hover_index = hover_index
                    line_num = hover_index + 1
                    self.listbox.tag_add('hover', f'{line_num}.0', f'{line_num}.end')
            else:
                # 滑鼠不在有效項目上，清除懸停效果
                if self._hover_index is not None:
                    line_num = self._hover_index + 1
                    self.listbox.tag_remove('hover', f'{line_num}.0', f'{line_num}.end')
                    self._hover_index = None
        except (ValueError, IndexError, tk.TclError):
            # 如果出錯，清除懸停效果
            if self._hover_index is not None:
                line_num = self._hover_index + 1
                self.listbox.tag_remove('hover', f'{line_num}.0', f'{line_num}.end')
                self._hover_index = None
    
    def _on_leave(self, event) -> None:
        """處理滑鼠離開事件"""
        # 清除懸停效果
        if self._hover_index is not None:
            line_num = self._hover_index + 1
            self.listbox.tag_remove('hover', f'{line_num}.0', f'{line_num}.end')
            self._hover_index = None
    
    def _on_click(self, event) -> None:
        """處理點擊事件"""
        if not self.on_item_select:
            return
        
        try:
            # 使用滑鼠位置獲取索引（更準確）
            index_str = self.listbox.index(f"@{event.x},{event.y}").split('.')[0]
            index = int(index_str) - 1
            if 0 <= index < len(self._playlist):
                # 清除懸停效果
                if self._hover_index is not None:
                    line_num = self._hover_index + 1
                    self.listbox.tag_remove('hover', f'{line_num}.0', f'{line_num}.end')
                    self._hover_index = None
                self.on_item_select(index)
        except (ValueError, IndexError, tk.TclError):
            pass
