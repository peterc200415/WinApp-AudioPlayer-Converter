"""
檔案處理工具模組
提供檔案操作相關的輔助函數
"""

import os
from typing import List, Optional


def get_srt_file_path(audio_file_path: str) -> str:
    """
    根據音頻檔案路徑獲取對應的 SRT 檔案路徑
    
    Args:
        audio_file_path: 音頻檔案路徑
    
    Returns:
        SRT 檔案路徑
    """
    return os.path.splitext(audio_file_path)[0] + ".srt"


def find_audio_files(directory: str, extensions: Optional[List[str]] = None) -> List[str]:
    """
    在指定目錄中查找所有音頻檔案
    
    Args:
        directory: 目錄路徑
        extensions: 音頻檔案副檔名列表，默認為 ['.mp3', '.m4a', '.wav', '.wma']
    
    Returns:
        音頻檔案路徑列表（已排序）
    """
    if extensions is None:
        extensions = ['.mp3', '.m4a', '.wav', '.wma']
    
    if not os.path.isdir(directory):
        return []
    
    audio_files = []
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path):
            _, ext = os.path.splitext(filename)
            if ext.lower() in extensions:
                audio_files.append(file_path)
    
    return sorted(audio_files)


def has_srt_file(audio_file_path: str) -> bool:
    """
    檢查音頻檔案是否有對應的 SRT 檔案
    
    Args:
        audio_file_path: 音頻檔案路徑
    
    Returns:
        如果存在 SRT 檔案則返回 True
    """
    srt_path = get_srt_file_path(audio_file_path)
    return os.path.exists(srt_path)
