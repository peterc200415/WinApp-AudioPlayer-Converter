# WinApp Audio Player Converter

一個功能完整的音頻播放器，支援字幕顯示和自動轉錄功能。

## 功能特性

- 🎵 播放多種音頻格式（MP3, M4A, WAV）
- 📝 顯示 SRT 字幕檔案
- 🎙️ 使用 Whisper 自動轉錄音頻為字幕
- 📋 播放列表管理
- 🔄 自動播放下一首
- ⏯️ 播放控制（播放/暫停/上一首/下一首）

## 項目結構

```
WinApp-AudioPlayer-Converter/
├── src/
│   ├── core/              # 核心業務邏輯
│   │   ├── audio_player.py
│   │   ├── subtitle_parser.py
│   │   └── transcriber.py
│   ├── ui/                # 用戶界面
│   │   ├── main_window.py
│   │   └── components/
│   └── utils/             # 工具模組
│       ├── config.py
│       ├── file_utils.py
│       └── time_utils.py
├── config/                # 配置文件
│   └── settings.json
├── requirements.txt
└── README.md
```

## 安裝

1. 安裝 Python 3.8 或更高版本

2. 安裝依賴：
```bash
pip install -r requirements.txt
```

3. 安裝 FFmpeg（用於音頻處理）：
   - Windows: 下載並添加到 PATH
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt-get install ffmpeg`

## 使用

運行應用程式（推薦從專案根目錄）：
```bash
python main.py
```

其他運行方式：
```bash
# 直接運行 src/main.py（已自動處理路徑）
python src/main.py

# 或使用模組方式運行
python -m src.main
```

### 基本操作

1. 點擊 "Play Directory" 選擇包含音頻檔案的目錄
2. 應用程式會自動掃描並播放音頻檔案
3. 如果有對應的 `.srt` 字幕檔案，會自動顯示
4. 使用控制按鈕進行播放/暫停/切換等操作

## 配置

編輯 `config/settings.json` 可以調整設定：

- `whisper_model`: Whisper 模型大小（tiny, base, small, medium, large）
- `device`: 計算設備（auto, cuda, cpu）
- `auto_transcribe`: 是否自動轉錄缺少字幕的音頻
- `font_size`: 字體大小
- `subtitle_font_size`: 字幕字體大小

## 模組說明

### Core 模組

- **AudioPlayer**: 音頻播放核心類，管理播放狀態和播放列表
- **SubtitleParser**: 解析 SRT 字幕檔案
- **Transcriber**: Whisper 轉錄封裝（單例模式）

### UI 組件

- **MainWindow**: 主視窗，整合所有組件
- **SubtitleDisplay**: 字幕顯示組件
- **PlaylistView**: 播放列表視圖
- **PlayerControls**: 播放控制按鈕
- **ProgressBar**: 播放進度條

### Utils 模組

- **Config**: 配置管理類
- **FileUtils**: 檔案操作工具
- **TimeUtils**: 時間格式化工具

## 開發

項目採用模組化架構設計：

- 使用類別封裝代替全局變數
- 清晰的模組分層（core/ui/utils）
- 回調機制實現組件通信
- 單例模式優化資源使用

## 授權

MIT License
