import pygame
import tkinter as tk
from tkinter import filedialog, scrolledtext
from pydub import AudioSegment
import threading
import os
import tempfile
import time
import re
from googletrans import Translator  # 引入翻譯庫
from googletrans.gtoken import TokenAcquirer

translator = Translator()
# Initialize pygame mixer
pygame.mixer.init()

# Initialize Tkinter application
root = tk.Tk()
root.title("Peter Audio Player")

# 調整視窗尺寸和背景色
root.geometry("600x400")
root.configure(bg="#2C3E50")

# 自定義按鈕樣式
button_style = {
    "font": ("Helvetica", 12, "bold"),
    "bg": "#1ABC9C",
    "fg": "#ECF0F1",
    "activebackground": "#16A085",
    "activeforeground": "#ECF0F1",
    "relief": tk.FLAT,
    "bd": 0,
    "padx": 10,
    "pady": 5
}

# 創建滾動文字區域來顯示 .srt 文件內容（英文字幕）
text_area_en = scrolledtext.ScrolledText(root, width=50, height=6, font=("Helvetica", 14), bg="#34495E", fg="#ECF0F1",
                                         relief=tk.FLAT)
text_area_en.pack(pady=10)

# 創建滾動文字區域來顯示中文翻譯
text_area_zh = scrolledtext.ScrolledText(root, width=50, height=6, font=("Helvetica", 14), bg="#34495E", fg="#ECF0F1",
                                         relief=tk.FLAT)
text_area_zh.pack(pady=10)

# Global variables to track pause state and the current file being played
is_paused = False
is_playing = False
current_file = None
subtitles_thread = None
translator = Translator()  # 初始化翻譯器




# Update the subtitles displayed in the text areas (both English and Chinese)
def update_subtitles(subtitles):
    global is_paused
    while pygame.mixer.music.get_busy() or is_paused:
        if not is_paused:
            current_time = pygame.mixer.music.get_pos() // 1000
            for start, end, text in subtitles:
                if start <= current_time <= end:
                    # 顯示英文字幕
                    text_area_en.delete(1.0, tk.END)
                    text_area_en.insert(tk.END, text)

                    # 顯示翻譯後的中文字幕
                    translated_text = None
                    attempts = 0
                    max_attempts = 3

                    while attempts < max_attempts:
                        try:
                            translated_text = translator.translate(text, src='en', dest='zh-tw').text  # 翻譯字幕
                            break  # 成功翻譯，跳出循環
                        except Exception as e:
                            print(f"翻譯失敗，重試中...（第 {attempts + 1} 次）")
                            time.sleep(2)  # 等待2秒後重試
                            attempts += 1

                    if translated_text:
                        text_area_zh.delete(1.0, tk.END)
                        text_area_zh.insert(tk.END, translated_text)
                    else:
                        text_area_zh.delete(1.0, tk.END)
                        text_area_zh.insert(tk.END, "翻譯失敗。")
                    break
        time.sleep(0.5)


# Define a function to parse .srt files for subtitles
def parse_srt(file_path):
    subtitles = []
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
        blocks = content.strip().split('\n\n')
        for block in blocks:
            lines = block.split('\n')
            if len(lines) >= 3:
                time_range = lines[1]
                text = ' '.join(lines[2:])
                start_time_str, end_time_str = time_range.split(' --> ')
                start_time = parse_srt_time(start_time_str)
                end_time = parse_srt_time(end_time_str)
                subtitles.append((start_time, end_time, text))
    return subtitles


# Parse the time format used in .srt files (hh:mm:ss,ms)
def parse_srt_time(time_str):
    hours, minutes, seconds = time_str.split(':')
    seconds, milliseconds = seconds.split(',')
    total_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    return total_seconds + int(milliseconds) / 1000


# Update the subtitles displayed in the text areas (both English and Chinese)
def update_subtitles(subtitles):
    global is_paused
    while pygame.mixer.music.get_busy() or is_paused:
        if not is_paused:
            current_time = pygame.mixer.music.get_pos() // 1000
            for start, end, text in subtitles:
                if start <= current_time <= end:
                    # 顯示英文字幕
                    text_area_en.delete(1.0, tk.END)
                    text_area_en.insert(tk.END, text)

                    # 顯示翻譯後的中文字幕
                    translated_text = translator.translate(text, src='en', dest='zh-tw').text  # 翻譯字幕
                    text_area_zh.delete(1.0, tk.END)
                    text_area_zh.insert(tk.END, translated_text)
                    break
        time.sleep(0.5)


# Define functions to control the music player
def play_music():
    global current_file, subtitles_thread, is_playing
    file_path = filedialog.askopenfilename(filetypes=[("Audio Files", "*.mp3 *.m4a")])
    if file_path:
        current_file = file_path
        is_playing = True

        # Look for a .srt file with the same name and display its contents
        srt_file_path = os.path.splitext(file_path)[0] + ".srt"
        subtitles = []
        if os.path.exists(srt_file_path):
            subtitles = parse_srt(srt_file_path)
        else:
            text_area_en.delete(1.0, tk.END)
            text_area_zh.delete(1.0, tk.END)
            text_area_en.insert(tk.END, "No associated .srt file found.")
            text_area_zh.insert(tk.END, "未找到相關的 .srt 文件。")

        # Play the audio file
        if file_path.endswith('.mp3'):
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            if subtitles:
                subtitles_thread = threading.Thread(target=update_subtitles, args=(subtitles,))
                subtitles_thread.start()
        elif file_path.endswith('.m4a'):
            play_m4a(file_path, subtitles)


def play_m4a(file_path, subtitles):
    global subtitles_thread, is_playing
    audio = AudioSegment.from_file(file_path)
    temp_wav_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_wav_file.close()  # Close the file so that it can be used by other processes
    audio.export(temp_wav_file.name, format="wav")

    if os.path.exists(temp_wav_file.name):
        pygame.mixer.music.load(temp_wav_file.name)
        pygame.mixer.music.play()
        is_playing = True
        if subtitles:
            subtitles_thread = threading.Thread(target=update_subtitles, args=(subtitles,))
            subtitles_thread.start()

        # Delete the temporary file after playback is complete
        def cleanup():
            # 等待音樂播放結束
            while pygame.mixer.music.get_busy() or is_paused:  # 確保暫停時不刪除
                pygame.time.wait(100)

            # 停止音樂播放並確保資源已釋放
            pygame.mixer.music.stop()
            # 等待一小段時間以確保資源完全釋放
            time.sleep(2)

            # 刪除臨時文件
            try:
                os.remove(temp_wav_file.name)
                print(f"Temporary file removed: {temp_wav_file.name}")
            except PermissionError:
                print(f"Failed to remove temporary file: {temp_wav_file.name}")

        threading.Thread(target=cleanup).start()
    else:
        print(f"Failed to create temporary file: {temp_wav_file.name}")


# Modify the pause function to toggle between pause and resume
def pause_resume_music():
    global is_paused, is_playing
    if is_playing:
        if not is_paused:
            pygame.mixer.music.pause()
            is_paused = True
        else:
            pygame.mixer.music.unpause()
            is_paused = False


# Define function to close the application
def close_application():
    pygame.mixer.music.stop()  # 停止播放音樂
    root.destroy()  # 關閉 Tkinter 視窗，結束應用程式


# Add buttons to the Tkinter interface and arrange them horizontally
play_button = tk.Button(root, text="Play", command=play_music, **button_style)
pause_button = tk.Button(root, text="Pause/Resume", command=pause_resume_music, **button_style)
close_button = tk.Button(root, text="Close", command=close_application, **button_style)

# 排列按鈕
play_button.pack(side=tk.LEFT, padx=20, pady=20)
pause_button.pack(side=tk.LEFT, padx=20, pady=20)
close_button.pack(side=tk.LEFT, padx=20, pady=20)

# Run the Tkinter application
root.mainloop()
