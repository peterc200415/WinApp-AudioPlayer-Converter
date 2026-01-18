import subprocess
import whisper
from tkinter import Tk, filedialog
import os

def extract_audio(video_path, audio_path):
    subprocess.run([
        "ffmpeg",
        "-i", video_path,
        "-q:a", "0",
        "-map", "a",
        audio_path,
        "-y"
    ])

def format_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

def main():
    # 使用者選擇檔案
    Tk().withdraw()  # 關閉主視窗
    video_path = filedialog.askopenfilename(
        title="選擇 MKV 影音檔",
        filetypes=[("MKV Files", "*.mkv"), ("All Files", "*.*")]
    )
    
    if not video_path:
        print("未選擇檔案。")
        return

    # 設定檔案路徑
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    audio_path = f"{base_name}.wav"
    srt_path = f"{base_name}.srt"

    # 提取音訊
    extract_audio(video_path, audio_path)

    # 加載 Whisper 模型
    model = whisper.load_model("base")

    # 進行語音識別
    result = model.transcribe(audio_path)

    # 保存字幕檔案
    with open(srt_path, "w", encoding="utf-8") as srt_file:
        for i, segment in enumerate(result["segments"]):
            start = segment["start"]
            end = segment["end"]
            text = segment["text"]
            srt_file.write(f"{i+1}\n")
            srt_file.write(f"{format_time(start)} --> {format_time(end)}\n")
            srt_file.write(f"{text}\n\n")
    
    print(f"字幕檔已保存為: {srt_path}")

if __name__ == "__main__":
    main()
