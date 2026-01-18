"""
播放控制組件
"""

import tkinter as tk
from typing import Optional, Callable


class PlayerControls:
    """播放控制組件類"""
    
    def __init__(self, parent: tk.Widget):
        """
        初始化播放控制組件
        
        Args:
            parent: 父組件
        """
        self.frame = tk.Frame(parent)
        
        # 回調函數
        self.on_play_directory: Optional[Callable[[], None]] = None
        self.on_pause: Optional[Callable[[], None]] = None
        self.on_next: Optional[Callable[[], None]] = None
        self.on_previous: Optional[Callable[[], None]] = None
        self.on_close: Optional[Callable[[], None]] = None
        
        # 創建按鈕
        self.play_directory_btn = tk.Button(
            self.frame, 
            text="Play Directory", 
            command=lambda: self.on_play_directory() if self.on_play_directory else None
        )
        self.pause_btn = tk.Button(
            self.frame, 
            text="Pause", 
            command=lambda: self.on_pause() if self.on_pause else None
        )
        self.next_btn = tk.Button(
            self.frame, 
            text="Next", 
            command=lambda: self.on_next() if self.on_next else None
        )
        self.previous_btn = tk.Button(
            self.frame, 
            text="Previous", 
            command=lambda: self.on_previous() if self.on_previous else None
        )
        self.close_btn = tk.Button(
            self.frame, 
            text="Close", 
            command=lambda: self.on_close() if self.on_close else None
        )
        
        # 布局按鈕
        self.play_directory_btn.grid(row=0, column=0, padx=5)
        self.previous_btn.grid(row=0, column=1, padx=5)
        self.pause_btn.grid(row=0, column=2, padx=5)
        self.next_btn.grid(row=0, column=3, padx=5)
        self.close_btn.grid(row=0, column=4, padx=5)
    
    def pack(self, **kwargs):
        """打包組件"""
        self.frame.pack(**kwargs)
    
    def grid(self, **kwargs):
        """網格布局"""
        self.frame.grid(**kwargs)
    
    def update_pause_button(self, is_paused: bool) -> None:
        """
        更新暫停按鈕文字
        
        Args:
            is_paused: 是否暫停
        """
        self.pause_btn.config(text="Play" if is_paused else "Pause")
