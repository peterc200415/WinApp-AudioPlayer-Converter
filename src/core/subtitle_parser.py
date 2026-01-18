"""
字幕解析器模組
提供 SRT 字幕檔案的解析功能
"""

import os
from typing import List, Tuple
from dataclasses import dataclass

from src.utils.time_utils import parse_srt_time


@dataclass
class Subtitle:
    """字幕數據類"""
    index: int
    start_time: float
    end_time: float
    text: str


class SubtitleParser:
    """字幕解析器類"""
    
    @staticmethod
    def parse_srt(file_path: str) -> List[Subtitle]:
        """
        解析 SRT 字幕檔案
        
        Args:
            file_path: SRT 檔案路徑
        
        Returns:
            字幕對象列表
        
        Raises:
            FileNotFoundError: 檔案不存在
            UnicodeDecodeError: 編碼錯誤
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"字幕檔案不存在: {file_path}")
        
        subtitles = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
        except UnicodeDecodeError:
            # 嘗試使用其他編碼
            with open(file_path, 'r', encoding='gbk') as file:
                content = file.read()
        
        blocks = content.strip().split('\n\n')
        
        for block in blocks:
            lines = [line.strip() for line in block.split('\n') if line.strip()]
            
            if len(lines) >= 3:
                try:
                    index = int(lines[0])
                    time_range = lines[1]
                    text = ' '.join(lines[2:])
                    
                    start_time_str, end_time_str = time_range.split(' --> ')
                    start_time = parse_srt_time(start_time_str)
                    end_time = parse_srt_time(end_time_str)
                    
                    subtitles.append(Subtitle(
                        index=index,
                        start_time=start_time,
                        end_time=end_time,
                        text=text
                    ))
                except (ValueError, IndexError) as e:
                    # 跳過格式不正確的區塊
                    print(f"跳過無效的字幕區塊: {e}")
                    continue
        
        return subtitles
    
    @staticmethod
    def find_subtitle_by_time(subtitles: List[Subtitle], current_time: float) -> Subtitle:
        """
        根據當前時間查找對應的字幕
        
        Args:
            subtitles: 字幕列表
            current_time: 當前時間（秒）
        
        Returns:
            匹配的字幕對象，如果沒有找到則返回 None
        """
        for subtitle in subtitles:
            if subtitle.start_time <= current_time <= subtitle.end_time:
                return subtitle
        return None
