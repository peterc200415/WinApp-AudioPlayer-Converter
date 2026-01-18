"""
字幕顯示組件
"""

import tkinter as tk
from tkinter import scrolledtext
from typing import Optional

from src.core.subtitle_parser import Subtitle


class SubtitleDisplay:
    """字幕顯示組件類"""
    
    def __init__(self, parent: tk.Widget, font_size: int = 14, width: int = 40, height: int = 4):
        """
        初始化字幕顯示組件
        
        Args:
            parent: 父組件
            font_size: 字體大小
            width: 寬度
            height: 高度
        """
        self.text_area = scrolledtext.ScrolledText(
            parent, 
            width=width, 
            height=height, 
            font=("Arial", font_size),
            wrap=tk.WORD,
            state='disabled'
        )
    
    def pack(self, **kwargs):
        """打包組件"""
        self.text_area.pack(**kwargs)
    
    def grid(self, **kwargs):
        """網格布局"""
        self.text_area.grid(**kwargs)
    
    def update_subtitle(self, subtitle: Optional[Subtitle]) -> None:
        """
        更新顯示的字幕
        
        Args:
            subtitle: 字幕對象，如果為 None 則清空
        """
        self.text_area.config(state='normal')
        self.text_area.delete(1.0, tk.END)
        
        if subtitle:
            self.text_area.insert(tk.END, subtitle.text)
        else:
            self.text_area.insert(tk.END, "未找到相關字幕文件")
        
        self.text_area.config(state='disabled')
    
    def clear(self) -> None:
        """清空字幕顯示"""
        self.text_area.config(state='normal')
        self.text_area.delete(1.0, tk.END)
        self.text_area.config(state='disabled')
