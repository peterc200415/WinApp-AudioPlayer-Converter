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
        
        # 配置標籤樣式
        self.listbox.tag_configure('bold', font=('Arial', 10, 'bold'))
        self.listbox.tag_configure('highlight', background='yellow')
        
        # 綁定點擊事件
        self.listbox.bind('<Button-1>', self._on_click)
        
        self._playlist: List[str] = []
        self._current_index: int = -1
    
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
        self.listbox.delete(1.0, tk.END)
        
        for i, file_path in enumerate(self._playlist):
            song_name = os.path.basename(file_path)
            
            if has_srt_file(file_path):
                self.listbox.insert(tk.END, f"{i + 1}. {song_name}\n", 'bold')
            else:
                self.listbox.insert(tk.END, f"{i + 1}. {song_name}\n")
        
        self._highlight_current()
    
    def _highlight_current(self) -> None:
        """高亮當前項目"""
        self.listbox.tag_remove('highlight', '1.0', tk.END)
        
        if 0 <= self._current_index < len(self._playlist):
            line_num = self._current_index + 1
            self.listbox.tag_add('highlight', f'{line_num}.0', f'{line_num}.end')
    
    def _on_click(self, event) -> None:
        """處理點擊事件"""
        if not self.on_item_select:
            return
        
        try:
            index_str = self.listbox.index("current").split('.')[0]
            index = int(index_str) - 1
            if 0 <= index < len(self._playlist):
                self.on_item_select(index)
        except (ValueError, IndexError):
            pass
