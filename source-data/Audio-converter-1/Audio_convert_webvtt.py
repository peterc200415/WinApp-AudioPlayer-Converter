import os
import whisper
from pydub import AudioSegment
import torch
import shutil
from tkinter import Tk
from tkinter.filedialog import askdirectory

# 檢查是否有可用的 GPU
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

# 檢查 ffmpeg 和 ffprobe 是否在 PATH 中
if shutil.which("ffmpeg") is None:
    raise RuntimeError("ffmpeg is not found in PATH")
if shutil.which("ffprobe") is None:
    raise RuntimeError("ffprobe is not found in PATH")

# 初始化 Whisper 模型，並指定設備（GPU 或 CPU）
model = whisper.load_model("base", device=device)

# 使用 tkinter 打開文件瀏覽器對話框選擇音頻文件根目錄
Tk().withdraw()  # 隱藏主窗口
root_audio_dir = askdirectory(title="請選擇音頻文件所在的根目錄路徑")

if not root_audio_dir:
    print("未選擇目錄，程序結束。")
    exit()

# 時間格式轉換函數，改為WebVTT格式
def format_timestamp(seconds):
    milliseconds = int((seconds - int(seconds)) * 1000)
    seconds = int(seconds)
    minutes = seconds // 60
    seconds = seconds % 60
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"

# 遞歸處理目錄及其子目錄中的所有音頻文件
for root, dirs, files in os.walk(root_audio_dir):
    for filename in files:
        if filename.endswith((".mp3", ".wav", ".m4a")):
            audio_path = os.path.join(root, filename)

            print(f"正在處理: {audio_path}")

            # 將音頻文件轉換為 WAV 格式（如果不是 WAV 格式）
            if not filename.endswith(".wav"):
                audio = AudioSegment.from_file(audio_path)
                # 臨時 WAV 文件路徑
                wav_path = os.path.join(root, f"{os.path.splitext(filename)[0]}.wav")
                audio.export(wav_path, format="wav")
            else:
                wav_path = audio_path

            # 使用 Whisper 模型轉錄音頻
            result = model.transcribe(wav_path)

            # 將轉錄文本保存到 .vtt 文件，與源文件在同一目錄
            vtt_path = os.path.join(root, f"{os.path.splitext(filename)[0]}.vtt")
            with open(vtt_path, "w", encoding="utf-8") as f:
                f.write("WEBVTT\n\n")
                for segment in result["segments"]:
                    start = format_timestamp(segment["start"])
                    end = format_timestamp(segment["end"])
                    text = segment["text"].strip()
                    f.write(f"{start} --> {end}\n")
                    f.write(f"{text}\n\n")

            print(f"已轉錄 {audio_path} 到 {vtt_path}")

            # 如果臨時創建了 WAV 文件，刪除它
            if not filename.endswith(".wav"):
                os.remove(wav_path)

print("所有文件處理完成。")
