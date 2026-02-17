# WinApp Audio Player Converter

WinApp 桌面音頻播放器，支援播放清單、字幕顯示與 Whisper 自動轉錄。

## 目前重點

- Qt 商業化 UI（`PySide6`）為預設入口
- 穩定字幕策略：固定使用 `base` 模型（避免切換模型造成不穩）
- 無字幕音檔可在播放中背景轉錄，不阻塞播放
- 支援 MP3 / M4A / WAV / WMA

## 快速開始

1. 安裝 Python 3.10+（建議）
2. 安裝套件：

```bash
pip install -r requirements.txt
```

3. 安裝 FFmpeg 並加入 PATH
   - Windows: `C:\ffmpeg\bin`
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt-get install ffmpeg`

4. 啟動：

```bash
python main.py
```

## 介面與操作

- `Open Folder`: 載入音樂目錄（重新載入會停止目前播放與背景轉錄）
- `Play / Prev / Next`: 播放控制
- 雙擊播放清單項目可直接切歌
- `Settings`: Whisper 模型、裝置、語言、字幕策略、字體大小
- 下方 `Log` 區會顯示轉錄/模型載入訊息（例如 `Loading Whisper model: base, device: cpu`）

## 字幕策略（Qt 版）

預設使用固定 `base` 分段轉錄：

1. 播放時即時分段排程，避免整首等待
2. 不切換模型，減少載入/切換帶來的錯誤風險

字幕區顯示規則：

- 正在播放的字幕：亮色 + 粗體
- 已播放字幕：淡色
- `Generating subtitles...` 在第一句真字幕出現後會移除

## GPU / CPU 說明

- `device=auto` 為 GPU-first；若 CUDA 不相容會自動回退 CPU
- 舊 GPU（例如 GTX 1060, `sm_61`）在新 PyTorch CUDA 版本可能不支援，會回退 CPU
- 回退狀態會寫到 Log

## 主要設定

編輯 `config/settings.json`：

- `whisper_model`: `tiny/base/small/medium/large`
- `device`: `auto/cuda/cpu`
- `whisper_language`: `auto/zh/en/...`
- `whisper_beam_size`, `whisper_best_of`: 解碼參數（越小越快）
- `subtitle_preview_model`: 預覽模型（固定 `base`）
- `subtitle_preview_seconds`: 每段秒數
- `subtitle_chunk_lead_seconds`: 提前排程秒數
- `enable_full_transcription`: 是否啟用 base 背景升級
- `base_chunk_seconds`: base 每段秒數
- `upgrade_start_after_seconds`: 分段升級起始秒數（預設 60）
- `subtitle_font_size`: 字幕字體大小
- `auto_transcribe_on_play`: 播放時自動轉錄

## 專案結構

```
src/
├── core/
│   ├── audio_player.py
│   ├── subtitle_parser.py
│   └── transcriber.py
├── ui/
│   └── ... (Tk 版)
├── ui_qt/
│   └── main_window.py (Qt 主介面)
└── utils/
    ├── config.py
    ├── file_utils.py
    └── time_utils.py
```

## 授權

MIT
