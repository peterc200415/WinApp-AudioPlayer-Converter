"""
配置管理模組
提供應用程式配置的載入和保存功能
"""

import json
import os
from typing import Dict, Any
from pathlib import Path


class Config:
    """配置管理類"""
    
    DEFAULT_CONFIG = {
        "whisper_model": "base",
        "device": "auto",  # "auto", "cuda", "cpu"
        "whisper_language": "auto",  # "auto" or explicit language code, e.g. "zh", "en"
        "whisper_beam_size": 1,
        "whisper_best_of": 1,
        "translation_target": "zh-TW",
        "font_size": 15,
        "subtitle_font_size": 14,
        "theme": "light",
        "auto_transcribe": False,  # 背景批次轉錄整個播放列表
        "auto_transcribe_on_play": True,  # 播放時自動轉錄缺失的字幕
        "enable_subtitle_preview": True,
        "subtitle_preview_seconds": 20,
        "subtitle_preview_model": "tiny",
        "enable_full_transcription": True,
        "subtitle_chunk_lead_seconds": 12,
        "base_chunk_seconds": 45,
        "upgrade_start_after_seconds": 60,
        "supported_formats": [".mp3", ".m4a", ".wav", ".wma"]
    }
    
    def __init__(self, config_path: str = "config/settings.json"):
        """
        初始化配置管理
        
        Args:
            config_path: 配置檔案路徑
        """
        self.config_path = config_path
        self._config = self.DEFAULT_CONFIG.copy()
        self.load()
    
    def load(self) -> None:
        """從檔案載入配置"""
        config_file = Path(self.config_path)
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    self._config.update(loaded_config)
            except (json.JSONDecodeError, IOError) as e:
                print(f"載入配置檔案失敗: {e}，使用默認配置")
        else:
            # 如果配置檔案不存在，創建默認配置檔案
            self.save()
    
    def save(self) -> None:
        """保存配置到檔案"""
        config_file = Path(self.config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
        except IOError as e:
            print(f"保存配置檔案失敗: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        獲取配置值
        
        Args:
            key: 配置鍵
            default: 默認值
        
        Returns:
            配置值
        """
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        設置配置值
        
        Args:
            key: 配置鍵
            value: 配置值
        """
        self._config[key] = value
    
    def get_all(self) -> Dict[str, Any]:
        """
        獲取所有配置
        
        Returns:
            所有配置的字典
        """
        return self._config.copy()
