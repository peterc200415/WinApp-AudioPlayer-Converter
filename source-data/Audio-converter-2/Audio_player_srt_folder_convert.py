import pygame
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk, font
from pydub import AudioSegment
import threading
import os
import tempfile
import time
import whisper
import torch

# Initialize pygame mixer
pygame.mixer.init()

# Initialize Whisper model
whisper_model = whisper.load_model("base")

# Define a global font for the Tkinter application
FONT_SIZE = 15
FONT_STYLE = ("Verdana", FONT_SIZE)

# Initialize Tkinter application
root = tk.Tk()
root.title("Peter Audio Player")

# Create a scrolled text area to display .srt file contents
text_area = scrolledtext.ScrolledText(root, width=40, height=5, font=FONT_STYLE)
text_area.pack(pady=10)

# Create a scrolled text area to display background conversion messages
conversion_messages = scrolledtext.ScrolledText(root, width=40, height=5, font=10)
conversion_messages.pack(pady=10)

# Define global variables to store current subtitles, audio file list, and current index
current_subtitles = []
current_audio_file = None
audio_files = []
current_index = -1
current_duration = 0
is_closing = False  # Flag to indicate if the program is closing
is_paused = False  # Flag to indicate if the playback is paused

# Define a function to parse .srt files for subtitles
def parse_srt(file_path):
    subtitles = []
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
        blocks = content.strip().split('\n\n')
        for block in blocks:
            lines = block.split('\n')
            if len(lines) >= 3:
                index = lines[0]
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

# Update the subtitles displayed in the text area
def update_subtitles():
    def update_text(text):
        text_area.delete(1.0, tk.END)
        text_area.insert(tk.END, text)

    while pygame.mixer.music.get_busy() and current_subtitles:
        if is_closing:
            return
        if not is_paused:
            current_time = pygame.mixer.music.get_pos() // 1000
            for start, end, text in current_subtitles:
                if start <= current_time <= end:
                    root.after(0, update_text, text)
                    break
        time.sleep(0.5)

# Update the progress bar
def update_progress_bar():
    def set_progress(value):
        progress_bar["value"] = value

    while pygame.mixer.music.get_busy():
        if is_closing:
            return
        if not is_paused:
            current_time = pygame.mixer.music.get_pos() // 1000
            root.after(0, set_progress, current_time)
        time.sleep(1)

# Define a function to play a single audio file
def play_single_file(file_path):
    global current_subtitles, current_audio_file, current_index, current_duration, is_paused
    current_audio_file = file_path
    is_paused = False  # Reset paused state

    # Clear the text area before playing the new file
    text_area.delete(1.0, tk.END)
    
    # Look for a .srt file with the same name and display its contents
    srt_file_path = os.path.splitext(file_path)[0] + ".srt"
    current_subtitles = []
    if os.path.exists(srt_file_path):
        current_subtitles = parse_srt(srt_file_path)
    else:
        text_area.insert(tk.END, "No associated .srt file found.")

    # Get the audio file duration
    if file_path.endswith('.mp3') or file_path.endswith('.m4a'):
        audio = AudioSegment.from_file(file_path)
        current_duration = len(audio) // 1000  # Duration in seconds
        progress_bar["maximum"] = current_duration

    # Play the audio file
    if file_path.endswith('.mp3'):
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        if current_subtitles:
            threading.Thread(target=update_subtitles).start()
        threading.Thread(target=update_progress_bar).start()
    elif file_path.endswith('.m4a'):
        play_m4a(file_path)

    highlight_current_song()

# Define functions to control the music player
def play_m4a(file_path):
    global current_subtitles, current_audio_file, current_duration, is_paused
    current_audio_file = file_path
    is_paused = False  # Reset paused state
    
    audio = AudioSegment.from_file(file_path)
    temp_wav_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_wav_file.close()  # Close the file so that it can be used by other processes
    audio.export(temp_wav_file.name, format="wav")
    current_duration = len(audio) // 1000  # Duration in seconds
    progress_bar["maximum"] = current_duration

    if os.path.exists(temp_wav_file.name):
        pygame.mixer.music.load(temp_wav_file.name)
        pygame.mixer.music.play()
        if current_subtitles:
            threading.Thread(target=update_subtitles).start()
        threading.Thread(target=update_progress_bar).start()
        # Delete the temporary file after playback is complete
        def cleanup():
            while pygame.mixer.music.get_busy():
                pygame.time.wait(100)
            pygame.mixer.music.stop()  # Stop audio playback
            retries = 3
            while retries > 0:
                try:
                    os.remove(temp_wav_file.name)
                    break
                except PermissionError:
                    retries -= 1
                    time.sleep(1)
                    if retries == 0:
                        print(f"Failed to remove temporary file: {temp_wav_file.name}")
        threading.Thread(target=cleanup).start()
    else:
        print(f"Failed to create temporary file: {temp_wav_file.name}")

def play_directory():
    global audio_files, current_index
    directory_path = filedialog.askdirectory()
    if directory_path:
        audio_files = sorted([os.path.join(directory_path, f) for f in os.listdir(directory_path) if f.endswith(('.mp3', '.m4a'))])
        if audio_files:
            current_index = 0
            update_song_list()
            threading.Thread(target=transcribe_audio_files).start()
            play_audio_files_sequentially(audio_files)

def transcribe_audio_files():
    for file_path in audio_files:
        srt_file_path = os.path.splitext(file_path)[0] + ".srt"
        if not os.path.exists(srt_file_path):
            convert_to_srt(file_path)
            root.after(0, update_song_list)  # Refresh song list after transcription is done

def convert_to_srt(audio_file):
    message = f"Transcribing {audio_file} using Whisper...\n"
    root.after(0, lambda: conversion_messages.insert(tk.END, message))
    try:
        result = whisper_model.transcribe(audio_file)
        srt_file_path = os.path.splitext(audio_file)[0] + ".srt"
        with open(srt_file_path, "w", encoding="utf-8") as srt_file:
            for i, segment in enumerate(result["segments"], start=1):
                start = segment["start"]
                end = segment["end"]
                text = segment["text"].strip()
                start_time_str = format_time(start)
                end_time_str = format_time(end)
                srt_file.write(f"{i}\n{start_time_str} --> {end_time_str}\n{text}\n\n")
        message = f"Transcription for {audio_file} completed.\n"
    except Exception as e:
        message = f"Error transcribing {audio_file}: {e}\n"
    root.after(0, lambda: conversion_messages.insert(tk.END, message))

def format_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

def play_audio_files_sequentially(audio_files):
    def play_next(index):
        if index < len(audio_files):
            global current_index
            current_index = index
            file_path = audio_files[index]
            play_single_file(file_path)
            pygame.mixer.music.set_endevent(pygame.USEREVENT)
            def on_music_end():
                while pygame.mixer.music.get_busy():
                    pygame.time.wait(100)
                play_next((index + 1) % len(audio_files))
            threading.Thread(target=on_music_end).start()

    play_next(0)

def next_music():
    global current_index, is_paused
    is_paused = False  # Reset paused state
    if current_index < len(audio_files) - 1:
        current_index += 1
        play_single_file(audio_files[current_index])
    else:
        current_index = 0
        play_single_file(audio_files[current_index])

def previous_music():
    global current_index, is_paused
    is_paused = False  # Reset paused state
    if current_index > 0:
        current_index -= 1
        play_single_file(audio_files[current_index])
    else:
        current_index = len(audio_files) - 1
        play_single_file(audio_files[current_index])

def pause_music():
    global is_paused
    if pygame.mixer.music.get_busy():
        if is_paused:
            pygame.mixer.music.unpause()
            is_paused = False
        else:
            pygame.mixer.music.pause()
            is_paused = True

def update_song_list():
    song_listbox.delete(1.0, tk.END)
    for i, file in enumerate(audio_files):
        song_name = os.path.basename(file)
        srt_file_path = os.path.splitext(file)[0] + ".srt"
        if os.path.exists(srt_file_path):
            song_listbox.insert(tk.END, f"{i + 1}. {song_name}\n", 'bold')
        else:
            song_listbox.insert(tk.END, f"{i + 1}. {song_name}\n")
    highlight_current_song()

def on_song_select(event):
    global current_index, is_paused
    is_paused = False  # Reset paused state
    current_index = int(event.widget.index("current").split('.')[0]) - 1
    play_single_file(audio_files[current_index])

def highlight_current_song():
    def highlight():
        song_listbox.tag_remove('highlight', '1.0', tk.END)
        song_listbox.tag_add('highlight', f'{current_index + 1}.0', f'{current_index + 1}.end')
    root.after(0, highlight)

def close_program():
    global is_closing
    is_closing = True
    pygame.mixer.music.stop()
    root.destroy()

# Add buttons to the Tkinter interface and arrange them horizontally
control_frame = tk.Frame(root)
control_frame.pack(pady=10)

play_directory_button = tk.Button(control_frame, text="Play Directory", command=play_directory)
pause_button = tk.Button(control_frame, text="Pause/Unpause", command=pause_music)
next_button = tk.Button(control_frame, text="Next", command=next_music)
previous_button = tk.Button(control_frame, text="Previous", command=previous_music)
close_button = tk.Button(control_frame, text="Close", command=close_program)

play_directory_button.grid(row=0, column=0, padx=5)
pause_button.grid(row=0, column=1, padx=5)
next_button.grid(row=0, column=2, padx=5)
previous_button.grid(row=0, column=3, padx=5)
close_button.grid(row=0, column=4, padx=5)

# Create progress bar
progress_frame = tk.Frame(root)
progress_frame.pack(pady=10)

progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", length=400, mode="determinate")
progress_bar.pack()

# Create song list box using Text widget with tags for bold and highlight
song_listbox = tk.Text(root, width=50, height=20)  # Adjusted height to 20
song_listbox.pack(pady=10)
song_listbox.tag_configure('bold', font=('Helvetica', 10, 'bold'))
song_listbox.tag_configure('highlight', background='yellow')
song_listbox.bind('<Button-1>', on_song_select)

# Run the Tkinter application
root.mainloop()
