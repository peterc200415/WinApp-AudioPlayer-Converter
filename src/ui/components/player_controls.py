"""
播放控制組件
"""

import tkinter as tk
from tkinter import ttk
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
        self.on_volume_changed: Optional[Callable[[float], None]] = None
        
        # 創建按鈕（使用 Unicode 符號）
        self.play_directory_btn = tk.Button(
            self.frame, 
            text="📁", 
            width=3,
            font=("Arial", 12),
            command=lambda: self.on_play_directory() if self.on_play_directory else None
        )
        self.previous_btn = tk.Button(
            self.frame, 
            text="⏮", 
            width=3,
            font=("Arial", 12),
            command=lambda: self.on_previous() if self.on_previous else None
        )
        self.pause_btn = tk.Button(
            self.frame, 
            text="▶",  # 初始狀態顯示播放圖標
            width=3,
            font=("Arial", 12),
            command=lambda: self.on_pause() if self.on_pause else None
        )
        self.next_btn = tk.Button(
            self.frame, 
            text="⏭", 
            width=3,
            font=("Arial", 12),
            command=lambda: self.on_next() if self.on_next else None
        )
        self.close_btn = tk.Button(
            self.frame, 
            text="✕", 
            width=3,
            font=("Arial", 12),
            command=lambda: self.on_close() if self.on_close else None
        )
        
        # 音量控制
        volume_frame = tk.Frame(self.frame)
        volume_label = tk.Label(volume_frame, text="🔊", font=("Arial", 10))
        volume_label.pack(side=tk.LEFT, padx=(0, 5))
        
        self.volume_var = tk.DoubleVar(value=100.0)
        self.volume_scale = ttk.Scale(
            volume_frame,
            from_=0.0,
            to=100.0,
            orient=tk.HORIZONTAL,
            length=100,
            variable=self.volume_var,
            command=self._on_volume_changed
        )
        self.volume_scale.pack(side=tk.LEFT)
        
        self.volume_value_label = tk.Label(volume_frame, text="100%", width=4)
        self.volume_value_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # 布局按鈕和控制
        self.play_directory_btn.grid(row=0, column=0, padx=5)
        self.previous_btn.grid(row=0, column=1, padx=5)
        self.pause_btn.grid(row=0, column=2, padx=5)
        self.next_btn.grid(row=0, column=3, padx=5)
        volume_frame.grid(row=0, column=4, padx=10)
        self.close_btn.grid(row=0, column=5, padx=5)
    
    def _on_volume_changed(self, value: str) -> None:
        """音量滑桿變更時觸發"""
        volume = float(value) / 100.0  # 轉換為 0.0-1.0
        self.volume_value_label.config(text=f"{int(float(value))}%")
        if self.on_volume_changed:
            self.on_volume_changed(volume)
    
    def pack(self, **kwargs):
        """打包組件"""
        self.frame.pack(**kwargs)
    
    def grid(self, **kwargs):
        """網格布局"""
        self.frame.grid(**kwargs)
    
    def update_pause_button(self, is_paused: bool) -> None:
        """
        更新暫停/播放按鈕圖標
        
        Args:
            is_paused: 是否暫停（True=暫停中顯示播放，False=播放中顯示暫停，None=未開始顯示播放）
        """
        self.pause_btn.config(text="▶" if is_paused else "⏸")
    
    def set_volume(self, volume: float) -> None:
        """
        設置音量滑桿值
        
        Args:
            volume: 音量值（0.0 - 1.0）
        """
        self.volume_var.set(volume * 100.0)
        self.volume_value_label.config(text=f"{int(volume * 100)}%")
