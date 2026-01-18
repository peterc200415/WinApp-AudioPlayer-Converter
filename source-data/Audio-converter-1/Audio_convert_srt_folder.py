import os
import whisper
from pydub import AudioSegment
import torch
import shutil
from tkinter import Tk
from tkinter.filedialog import askdirectory

# 检查是否有可用的 GPU
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

# 检查 ffmpeg 和 ffprobe 是否在 PATH 中
if shutil.which("ffmpeg") is None:
    raise RuntimeError("ffmpeg is not found in PATH")
if shutil.which("ffprobe") is None:
    raise RuntimeError("ffprobe is not found in PATH")

# 初始化 Whisper 模型，并指定设备（GPU 或 CPU）
model = whisper.load_model("base", device=device)

# 使用 tkinter 打开文件浏览器对话框选择音频文件根目录
Tk().withdraw()  # 隐藏主窗口
root_audio_dir = askdirectory(title="请选择音频文件所在的根目录路径")

if not root_audio_dir:
    print("未选择目录，程序结束。")
    exit()


# 时间格式转换函数
def format_timestamp(seconds):
    milliseconds = int((seconds - int(seconds)) * 1000)
    seconds = int(seconds)
    minutes = seconds // 60
    seconds = seconds % 60
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


# 递归处理目录及其子目录中的所有音频文件
for root, dirs, files in os.walk(root_audio_dir):
    for filename in files:
        if filename.endswith((".mp3", ".wav", ".m4a")):
            audio_path = os.path.join(root, filename)

            print(f"正在处理: {audio_path}")

            # 将音频文件转换为 WAV 格式（如果不是 WAV 格式）
            if not filename.endswith(".wav"):
                audio = AudioSegment.from_file(audio_path)
                # 临时 WAV 文件路径
                wav_path = os.path.join(root, f"{os.path.splitext(filename)[0]}.wav")
                audio.export(wav_path, format="wav")
            else:
                wav_path = audio_path

            # 使用 Whisper 模型转录音频
            result = model.transcribe(wav_path)

            # 将转录文本保存到 .srt 文件，与源文件在同一目录
            srt_path = os.path.join(root, f"{os.path.splitext(filename)[0]}.srt")
            with open(srt_path, "w", encoding="utf-8") as z:
                for i, segment in enumerate(result["segments"]):
                    start = format_timestamp(segment["start"])
                    end = format_timestamp(segment["end"])
                    text = segment["text"].strip()
                    z.write(f"{i + 1}\n")
                    z.write(f"{start} --> {end}\n")
                    z.write(f"{text}\n\n")

            print(f"已转录 {audio_path} 到 {srt_path}")

            # 如果临时创建了 WAV 文件，删除它
            if not filename.endswith(".wav"):
                os.remove(wav_path)

print("所有文件处理完成。")
