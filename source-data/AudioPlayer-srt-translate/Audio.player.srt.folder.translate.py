import pygame
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk
from pydub import AudioSegment
import threading
import os
import tempfile
import time
import re
from googletrans import Translator

# Initialize pygame mixer
pygame.mixer.init()

# Initialize Tkinter application with ttk theme
root = tk.Tk()
root.title("Peter Audio Player")
root.geometry("800x400")  # 调整窗口大小

# Apply ttk theme
style = ttk.Style()
style.theme_use('clam')  # 可以尝试 'clam', 'alt', 'default', 'classic'

# 设置颜色风格
primary_color = "#2c3e50"  # 主色调：深蓝色
secondary_color = "#34495e"  # 次色调
accent_color = "#e74c3c"  # 强调色：红色
text_color = "#ecf0f1"  # 文字颜色：白色

# 设置窗口背景颜色
root.configure(bg=primary_color)

# 定义全局字体
FONT_SIZE = 12
FONT_STYLE = ("Arial", FONT_SIZE)
SUBTITLE_FONT_SIZE = 14  # 字幕区域的字体大小
SUBTITLE_FONT_STYLE = ("Arial", SUBTITLE_FONT_SIZE)

# Create frames for better layout management
top_frame = tk.Frame(root, bg=primary_color)
top_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

middle_frame = tk.Frame(root, bg=primary_color)
middle_frame.pack(fill=tk.BOTH, expand=True)

bottom_frame = tk.Frame(root, bg=primary_color)
bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)

# Create a scrolled text area to display .srt file contents
text_area = scrolledtext.ScrolledText(top_frame, width=40, height=4, font=SUBTITLE_FONT_STYLE, wrap=tk.WORD, bg=secondary_color, fg=text_color)
text_area.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

# 创建一个新的文本区域，用于显示翻译后的字幕
translated_text_area = scrolledtext.ScrolledText(top_frame, width=40, height=4, font=SUBTITLE_FONT_STYLE, wrap=tk.WORD, bg=secondary_color, fg=text_color)
translated_text_area.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

# 调整 top_frame 的网格布局
top_frame.grid_columnconfigure(0, weight=1)
top_frame.grid_columnconfigure(1, weight=1)
top_frame.grid_rowconfigure(0, weight=1)

# Define global variables
current_subtitles = []
current_audio_file = None
audio_files = []
current_index = -1
current_duration = 0
is_closing = False
is_paused = False

translator = Translator(service_urls=['translate.google.com'])  # 初始化翻译器

# 定义解析 .srt 文件的函数
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

# 解析 .srt 文件中的时间格式 (hh:mm:ss,ms)
def parse_srt_time(time_str):
    hours, minutes, seconds = time_str.split(':')
    seconds, milliseconds = seconds.split(',')
    total_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    return total_seconds + int(milliseconds) / 1000

# 定义更新字幕的函数
def update_subtitles():
    def update_text_area(text):
        text_area.delete(1.0, tk.END)
        text_area.insert(tk.END, text)

    def update_translated_text_area(translated_text):
        translated_text_area.delete(1.0, tk.END)
        translated_text_area.insert(tk.END, translated_text)

    while pygame.mixer.music.get_busy() and current_subtitles and not is_closing:
        if is_paused:
            time.sleep(0.5)
            continue
        current_time = pygame.mixer.music.get_pos() // 1000  # 将毫秒转换为秒
        for start, end, text in current_subtitles:
            if start <= current_time <= end:
                root.after(0, update_text_area, text)  # 更新字幕区域的内容
                # 翻译字幕为繁体中文
                translated = translator.translate(text, dest='zh-tw').text
                root.after(0, update_translated_text_area, translated)  # 更新翻译后的字幕区域
                break
        time.sleep(0.5)  # 每隔0.5秒检查一次时间

# 定义更新进度条的函数
def update_progress_bar():
    while pygame.mixer.music.get_busy() and not is_closing:
        if not is_paused:
            current_time = pygame.mixer.music.get_pos() // 1000  # 获取当前播放时间，转换为秒
            root.after(0, progress_bar.config, {"value": current_time})  # 更新进度条
        time.sleep(1)  # 每秒更新一次

# 定义更新歌曲列表的函数
def update_song_list():
    song_listbox.delete(1.0, tk.END)  # 清空当前列表
    for i, file in enumerate(audio_files):
        song_name = os.path.basename(file)
        srt_file_path = os.path.splitext(file)[0] + ".srt"
        if os.path.exists(srt_file_path):
            song_listbox.insert(tk.END, f"{i + 1}. {song_name}\n", 'bold')  # 使用加粗显示
        else:
            song_listbox.insert(tk.END, f"{i + 1}. {song_name}\n")
    highlight_current_song()  # 高亮当前歌曲

# 定义播放单个音频文件的函数
def play_single_file(file_path):
    global current_subtitles, current_audio_file, current_index, current_duration, is_paused, temp_wav_file
    current_audio_file = file_path
    is_paused = False  # 重置暂停状态

    # 清空字幕区域
    def clear_text_areas():
        text_area.delete(1.0, tk.END)
        translated_text_area.delete(1.0, tk.END)

    root.after(0, clear_text_areas)  # 使用 root.after 保证在主线程上清空字幕区域

    # 查找与音频文件同名的 .srt 文件并显示其内容
    srt_file_path = os.path.splitext(file_path)[0] + ".srt"
    current_subtitles = []
    if os.path.exists(srt_file_path):
        current_subtitles = parse_srt(srt_file_path)
    else:
        def no_srt_message():
            text_area.insert(tk.END, "No associated .srt file found.")
            translated_text_area.insert(tk.END, "未找到相关的 .srt 字幕文件。")
        root.after(0, no_srt_message)  # 显示没有 .srt 文件的消息

    # 获取音频文件的时长
    if file_path.lower().endswith(('.mp3', '.m4a', '.wav')):
        audio = AudioSegment.from_file(file_path)
        current_duration = len(audio) // 1000  # 时长以秒为单位
        progress_bar["maximum"] = current_duration

    # 播放音频文件
    if file_path.lower().endswith('.mp3'):
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        if current_subtitles:
            threading.Thread(target=update_subtitles).start()  # 更新字幕
        threading.Thread(target=update_progress_bar).start()  # 更新进度条
    elif file_path.lower().endswith('.m4a'):
        play_m4a(file_path)
    elif file_path.lower().endswith('.wav'):
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        if current_subtitles:
            threading.Thread(target=update_subtitles).start()
        threading.Thread(target=update_progress_bar).start()

    highlight_current_song()

# 定义处理 .m4a 文件的函数
def play_m4a(file_path):
    global current_subtitles, current_audio_file, current_duration, is_paused, temp_wav_file
    current_audio_file = file_path
    is_paused = False  # 重置暂停状态

    audio = AudioSegment.from_file(file_path)
    temp_wav_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_wav_file.close()  # 关闭文件以便其他进程使用
    audio.export(temp_wav_file.name, format="wav")  # 将 .m4a 文件转换为 .wav
    current_duration = len(audio) // 1000  # 时长以秒为单位
    progress_bar["maximum"] = current_duration

    if os.path.exists(temp_wav_file.name):
        pygame.mixer.music.load(temp_wav_file.name)
        pygame.mixer.music.play()
        if current_subtitles:
            threading.Thread(target=update_subtitles).start()  # 更新字幕
        threading.Thread(target=update_progress_bar).start()  # 更新进度条

        # 播放结束后删除临时文件
        def cleanup():
            global is_closing
            while True:
                if is_paused or is_closing:
                    pygame.time.wait(100)
                    continue
                pos = pygame.mixer.music.get_pos()
                if pos == -1 or is_closing:
                    break
                pygame.time.wait(100)
            pygame.mixer.music.stop()  # 停止音乐播放
            pygame.mixer.music.unload()  # 卸载音乐，释放文件资源
            try:
                os.remove(temp_wav_file.name)  # 删除临时文件
            except PermissionError:
                time.sleep(0.1)
                os.remove(temp_wav_file.name)
        threading.Thread(target=cleanup).start()
    else:
        print(f"无法创建临时文件: {temp_wav_file.name}")

# 定义高亮当前歌曲的函数
def highlight_current_song():
    def highlight():
        song_listbox.tag_remove('highlight', '1.0', tk.END)  # Clear previous highlights
        song_listbox.tag_add('highlight', f'{current_index + 1}.0', f'{current_index + 1}.end')  # Highlight current song
    if not is_closing:
        root.after(0, highlight)

# 定义暂停/继续播放的函数
def pause_music():
    global is_paused
    if is_paused:
        pygame.mixer.music.unpause()  # 恢复播放
        pause_button.config(text="Pause")  # 将按钮文本改回 "Pause"
        is_paused = False
    else:
        pygame.mixer.music.pause()  # 暂停音乐
        pause_button.config(text="Play")  # 将按钮文本改为 "Play"
        is_paused = True

# 定义播放下一首音乐的函数
def next_music():
    global current_index, is_paused
    is_paused = False  # 重置暂停状态
    if current_index >= 0 and current_index < len(audio_files) - 1:
        current_index += 1
        play_single_file(audio_files[current_index])
    else:
        current_index = 0  # 从第一首歌开始
        play_single_file(audio_files[current_index])

# 定义播放上一首音乐的函数
def previous_music():
    global current_index, is_paused
    is_paused = False  # 重置暂停状态
    if current_index > 0:
        current_index -= 1
        play_single_file(audio_files[current_index])
    else:
        current_index = len(audio_files) - 1  # 从最后一首歌开始
        play_single_file(audio_files[current_index])

# 定义函数来播放整个文件夹中的音频文件
def play_directory():
    global audio_files, current_index
    directory_path = filedialog.askdirectory()
    if directory_path:
        # Get all .mp3, .m4a, and .wav files in the directory
        audio_files = sorted([os.path.join(directory_path, f) for f in os.listdir(directory_path) if f.lower().endswith(('.mp3', '.m4a', '.wav'))])
        if audio_files:
            current_index = 0  # Start from the first file
            play_audio_files_sequentially(audio_files)
            update_song_list()

# 播放文件夹中的音频文件，按顺序播放
def play_audio_files_sequentially(audio_files):
    def play_next(index):
        if index < len(audio_files) and not is_closing:
            global current_index
            current_index = index
            file_path = audio_files[index]
            play_single_file(file_path)
            # Set event to play the next file after the current one finishes
            def on_music_end():
                global is_closing
                while True:
                    if is_paused or is_closing:
                        pygame.time.wait(100)
                        continue
                    pos = pygame.mixer.music.get_pos()
                    if pos == -1 or is_closing:
                        break
                    pygame.time.wait(100)
                if not is_closing:
                    root.after(0, play_next, (index + 1) % len(audio_files))
            threading.Thread(target=on_music_end).start()
    play_next(0)

# 定义处理歌曲选择的函数
def on_song_select(event):
    global current_index
    # Get the line number of the selected position
    index = int(event.widget.index("current").split('.')[0]) - 1
    if 0 <= index < len(audio_files):
        current_index = index
        play_single_file(audio_files[current_index])

# 定义关闭程序的函数
def close_program():
    global is_closing
    is_closing = True  # 设置标志，表示程序正在关闭
    pygame.mixer.music.stop()  # 停止音乐播放
    root.destroy()  # 关闭 Tkinter 应用窗口

# 添加控制按钮，移除了 Play 按钮
control_frame = tk.Frame(bottom_frame, bg=primary_color)
control_frame.pack(pady=10)

play_directory_button = tk.Button(control_frame, text="Play Directory", command=play_directory, bg=accent_color, fg=text_color, font=FONT_STYLE, width=12)
previous_button = tk.Button(control_frame, text="Previous", command=previous_music, bg=accent_color, fg=text_color, font=FONT_STYLE, width=8)
pause_button = tk.Button(control_frame, text="Pause", command=pause_music, bg=accent_color, fg=text_color, font=FONT_STYLE, width=8)
next_button = tk.Button(control_frame, text="Next", command=next_music, bg=accent_color, fg=text_color, font=FONT_STYLE, width=8)
close_button = tk.Button(control_frame, text="Close", command=close_program, bg=accent_color, fg=text_color, font=FONT_STYLE, width=8)

play_directory_button.grid(row=0, column=0, padx=5)
previous_button.grid(row=0, column=1, padx=5)
pause_button.grid(row=0, column=2, padx=5)
next_button.grid(row=0, column=3, padx=5)
close_button.grid(row=0, column=4, padx=5)

# Create progress bar
progress_frame = tk.Frame(bottom_frame, bg=primary_color)
progress_frame.pack(pady=10, padx=10, fill=tk.X)

progress_bar_style = ttk.Style()
progress_bar_style.theme_use('clam')
progress_bar_style.configure("Custom.Horizontal.TProgressbar", troughcolor=secondary_color, background=accent_color)

progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", length=400, mode="determinate", style="Custom.Horizontal.TProgressbar")
progress_bar.pack(fill=tk.X, expand=True)

# Create song list box using Text widget with tags for bold and highlight
song_listbox = tk.Text(middle_frame, width=60, height=10, font=FONT_STYLE, wrap=tk.WORD, bg=secondary_color, fg=text_color)
song_listbox.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
song_listbox.tag_configure('bold', font=('Arial', 10, 'bold'))
song_listbox.tag_configure('highlight', background='black')
song_listbox.bind('<Button-1>', on_song_select)

# 设置滚动条（如果需要）
song_list_scrollbar = tk.Scrollbar(song_listbox)
song_list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
song_listbox.config(yscrollcommand=song_list_scrollbar.set)
song_list_scrollbar.config(command=song_listbox.yview)

# Run the Tkinter application
root.mainloop()
