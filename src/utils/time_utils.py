"""
時間格式處理工具模組
提供 SRT 時間格式的解析和格式化功能
"""

from typing import Tuple


def parse_srt_time(time_str: str) -> float:
    """
    解析 SRT 時間格式 (hh:mm:ss,ms) 為秒數
    
    Args:
        time_str: SRT 格式時間字符串，例如 "00:01:23,456"
    
    Returns:
        總秒數（浮點數）
    
    Raises:
        ValueError: 時間格式不正確
    """
    try:
        hours, minutes, seconds = time_str.split(':')
        seconds, milliseconds = seconds.split(',')
        total_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
        return total_seconds + int(milliseconds) / 1000
    except (ValueError, IndexError) as e:
        raise ValueError(f"無效的時間格式: {time_str}") from e


def format_time(seconds: float) -> str:
    """
    將秒數格式化為 SRT 時間格式 (hh:mm:ss,ms)
    
    Args:
        seconds: 秒數（浮點數）
    
    Returns:
        SRT 格式時間字符串，例如 "00:01:23,456"
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"


def format_timestamp(seconds: float) -> str:
    """
    將秒數格式化為時間戳格式 (hh:mm:ss)
    用於顯示用途
    
    Args:
        seconds: 秒數（浮點數）
    
    Returns:
        時間戳字符串，例如 "01:23:45"
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02}:{minutes:02}:{secs:02}"
