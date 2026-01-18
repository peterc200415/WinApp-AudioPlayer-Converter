"""
語音轉錄器模組
使用 Whisper 模型進行音頻轉錄
"""

import os
import whisper
import torch
from typing import Dict, Optional
from threading import Lock

from src.utils.time_utils import format_time


class Transcriber:
    """語音轉錄器類（單例模式）"""
    
    _instance: Optional['Transcriber'] = None
    _lock = Lock()
    
    def __new__(cls):
        """實現單例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化轉錄器"""
        if hasattr(self, '_initialized'):
            return
        
        self._model: Optional[whisper.Whisper] = None
        self._model_name: Optional[str] = None
        self._device: Optional[str] = None
        self._initialized = True
    
    def _get_device(self, device_preference: str = "auto") -> str:
        """
        確定使用的設備（GPU 或 CPU）
        
        Args:
            device_preference: 設備偏好 ("auto", "cuda", "cpu")
        
        Returns:
            設備名稱
        """
        if device_preference == "cuda" and torch.cuda.is_available():
            return "cuda"
        elif device_preference == "cpu":
            return "cpu"
        else:
            # auto 模式
            return "cuda" if torch.cuda.is_available() else "cpu"
    
    def load_model(self, model_name: str = "base", device: str = "auto") -> None:
        """
        載入 Whisper 模型
        
        Args:
            model_name: 模型名稱 (tiny, base, small, medium, large)
            device: 設備 ("auto", "cuda", "cpu")
        """
        if self._model is not None and self._model_name == model_name:
            return  # 模型已載入
        
        self._device = self._get_device(device)
        print(f"載入 Whisper 模型: {model_name}, 設備: {self._device}")
        
        self._model = whisper.load_model(model_name, device=self._device)
        self._model_name = model_name
    
    def transcribe(self, audio_path: str, model_name: str = "base", 
                   device: str = "auto") -> Dict:
        """
        轉錄音頻檔案
        
        Args:
            audio_path: 音頻檔案路徑
            model_name: 模型名稱
            device: 設備偏好
        
        Returns:
            Whisper 轉錄結果字典
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音頻檔案不存在: {audio_path}")
        
        self.load_model(model_name, device)
        
        if self._model is None:
            raise RuntimeError("模型未載入")
        
        result = self._model.transcribe(audio_path)
        return result
    
    def transcribe_to_srt(self, audio_path: str, output_path: Optional[str] = None,
                          model_name: str = "base", device: str = "auto") -> str:
        """
        轉錄音頻並保存為 SRT 檔案
        
        Args:
            audio_path: 音頻檔案路徑
            output_path: 輸出 SRT 檔案路徑，如果為 None 則自動生成
            model_name: 模型名稱
            device: 設備偏好
        
        Returns:
            輸出的 SRT 檔案路徑
        """
        if output_path is None:
            base_path = os.path.splitext(audio_path)[0]
            output_path = f"{base_path}.srt"
        
        result = self.transcribe(audio_path, model_name, device)
        
        with open(output_path, 'w', encoding='utf-8') as srt_file:
            for i, segment in enumerate(result["segments"], start=1):
                start = segment["start"]
                end = segment["end"]
                text = segment["text"].strip()
                start_time_str = format_time(start)
                end_time_str = format_time(end)
                srt_file.write(f"{i}\n{start_time_str} --> {end_time_str}\n{text}\n\n")
        
        return output_path
    
    @property
    def device(self) -> Optional[str]:
        """獲取當前使用的設備"""
        return self._device
    
    @property
    def model_name(self) -> Optional[str]:
        """獲取當前載入的模型名稱"""
        return self._model_name
