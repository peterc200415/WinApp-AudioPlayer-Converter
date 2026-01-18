"""
進度條組件
"""

import tkinter as tk
from tkinter import ttk


class ProgressBar:
    """進度條組件類"""
    
    def __init__(self, parent: tk.Widget, length: int = 400):
        """
        初始化進度條
        
        Args:
            parent: 父組件
            length: 長度
        """
        self.frame = tk.Frame(parent)
        self.progress_bar = ttk.Progressbar(
            self.frame, 
            orient="horizontal", 
            length=length, 
            mode="determinate"
        )
        self.progress_bar.pack()
    
    def pack(self, **kwargs):
        """打包組件"""
        self.frame.pack(**kwargs)
    
    def grid(self, **kwargs):
        """網格布局"""
        self.frame.grid(**kwargs)
    
    def set_maximum(self, value: float) -> None:
        """
        設置最大值
        
        Args:
            value: 最大值
        """
        self.progress_bar["maximum"] = value
    
    def set_value(self, value: float) -> None:
        """
        設置當前值
        
        Args:
            value: 當前值
        """
        self.progress_bar["value"] = value
    
    def reset(self) -> None:
        """重置進度條"""
        self.progress_bar["value"] = 0
