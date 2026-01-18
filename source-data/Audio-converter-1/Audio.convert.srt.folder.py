import os
import whisper
from pydub import AudioSegment
import torch
import shutil
import threading
import queue
import tkinter as tk
from tkinter import filedialog

# 檢查是否有可用的 GPU
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"使用設備: {device}")

# 檢查 ffmpeg 和 ffprobe 是否在 PATH 中
if shutil.which("ffmpeg") is None:
    raise RuntimeError("找不到 ffmpeg 在 PATH 中")
if shutil.which("ffprobe") is None:
    raise RuntimeError("找不到 ffprobe 在 PATH 中")

# 初始化 Whisper 模型，並指定設備（GPU 或 CPU）
model = whisper.load_model("base", device=device)

# 創建主窗口
root = tk.Tk()
root.title("音頻轉錄處理進度")
root.geometry("600x400")

# 創建文本框，用於顯示日志
text_log = tk.Text(root, wrap='word', state='disabled')
text_log.pack(expand=True, fill='both')

# 創建一個階階，用於線程間通信
log_queue = queue.Queue()

# 時間格式轉換函數
def format_timestamp(seconds):
    milliseconds = int((seconds - int(seconds)) * 1000)
    seconds = int(seconds)
    minutes = seconds // 60
    seconds = seconds % 60
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

# 日志更新函數
def update_log():
    while not log_queue.empty():
        msg = log_queue.get_nowait()
        text_log.configure(state='normal')
        text_log.insert('end', msg + '\n')
        text_log.configure(state='disabled')
        text_log.see('end')  # 自動滾動到底部
    root.after(100, update_log)

# 後台處理函數
def process_files(root_audio_dir):
    # 遞歷處理目錄及其子目錄中的所有音頻檔案
    for root_dir, dirs, files in os.walk(root_audio_dir):
        for filename in files:
            if filename.endswith((".mp3", ".wav", ".m4a")):
                audio_path = os.path.join(root_dir, filename)
                log_queue.put(f"正在處理: {audio_path}")

                try:
                    # 將音頻檔案轉換為 WAV 格式（如果不是 WAV 格式）
                    if not filename.endswith(".wav"):
                        audio = AudioSegment.from_file(audio_path)
                        # 臨時 WAV 檔案路徑
                        wav_path = os.path.join(root_dir, f"{os.path.splitext(filename)[0]}.wav")
                        audio.export(wav_path, format="wav")
                    else:
                        wav_path = audio_path

                    # 使用 Whisper 模型轉錄音頻
                    result = model.transcribe(wav_path)

                    # 將轉錄文本保存到 .srt 檔案，與源檔案在同一目錄
                    srt_path = os.path.join(root_dir, f"{os.path.splitext(filename)[0]}.srt")
                    with open(srt_path, "w", encoding="utf-8") as z:
                        for i, segment in enumerate(result["segments"]):
                            start = format_timestamp(segment["start"])
                            end = format_timestamp(segment["end"])
                            text = segment["text"].strip()
                            z.write(f"{i + 1}\n")
                            z.write(f"{start} --> {end}\n")
                            z.write(f"{text}\n\n")

                    log_queue.put(f"已轉錄 {audio_path} 到 {srt_path}")

                    # 如果臨時創建了 WAV 檔案，刪除它
                    if not filename.endswith(".wav"):
                        os.remove(wav_path)

                except Exception as e:
                    log_queue.put(f"處理 {audio_path} 時發生錯誤: {str(e)}")

    log_queue.put("所有檔案處理完成。")

# 選擇目錄並開始處理
def start_processing():
    root_audio_dir = filedialog.askdirectory(title="請選擇音頻檔案所在的根目錄路徑")
    if not root_audio_dir:
        log_queue.put("未選擇目錄，程式終止。")
        return

    # 啟動後台線程處理檔案
    threading.Thread(target=process_files, args=(root_audio_dir,), daemon=True).start()

# 添加開始按鈕
start_button = tk.Button(root, text="選擇目錄並開始處理", command=start_processing)
start_button.pack(pady=10)

# 添加結束按鈕
end_button = tk.Button(root, text="結束", command=root.quit)
end_button.pack(pady=10)

# 啟動日志更新
update_log()

# 運行主循環
root.mainloop()