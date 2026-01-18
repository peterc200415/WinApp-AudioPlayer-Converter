import pygame
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk
from pydub import AudioSegment
import threading
import os
import tempfile
import time
import re

# Initialize pygame mixer
pygame.mixer.init()

# Define a global font for the Tkinter application
FONT_SIZE = 15
FONT_STYLE = ("Helvetica", FONT_SIZE)

# Initialize Tkinter application
root = tk.Tk()
root.title("Peter Audio Player")

# Create a scrolled text area to display .srt file contents
text_area = scrolledtext.ScrolledText(root, width=40, height=5, font=FONT_STYLE)
text_area.pack(pady=10)

# Define global variables to store current subtitles, audio file list, and current index
current_subtitles = []
current_audio_file = None
audio_files = []
current_index = -1
current_duration = 0

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

# Update the subtitles displayed in the text area
def update_subtitles():
    def update_text(text):
        text_area.delete(1.0, tk.END)
        text_area.insert(tk.END, text)

    while pygame.mixer.music.get_busy() and current_subtitles:
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
        current_time = pygame.mixer.music.get_pos() // 1000
        root.after(0, set_progress, current_time)
        time.sleep(1)

# Define a function to play a single audio file
def play_single_file(file_path):
    global current_subtitles, current_audio_file, current_index, current_duration
    current_audio_file = file_path

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
def play_music():
    global audio_files, current_index
    file_path = filedialog.askopenfilename(filetypes=[("Audio Files", "*.mp3 *.m4a")])
    if file_path:
        audio_files = [file_path]
        current_index = 0
        play_single_file(file_path)
        update_song_list()

def play_m4a(file_path):
    global current_subtitles, current_audio_file, current_duration
    current_audio_file = file_path
    
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
            try:
                os.remove(temp_wav_file.name)
            except PermissionError:
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
            play_audio_files_sequentially(audio_files)
            update_song_list()

def play_audio_files_sequentially(audio_files):
    def play_next(index):
        if index < len(audio_files):
            global current_index
            current_index = index
            file_path = audio_files[index]
            play_single_file(file_path)
            # Setup the event to play the next file when the current file ends
            pygame.mixer.music.set_endevent(pygame.USEREVENT)
            def on_music_end():
                while pygame.mixer.music.get_busy():
                    pygame.time.wait(100)
                play_next((index + 1) % len(audio_files))
            threading.Thread(target=on_music_end).start()

    play_next(0)

def next_music():
    global current_index
    if current_index >= 0 and current_index < len(audio_files) - 1:
        current_index += 1
        play_single_file(audio_files[current_index])
    else:
        current_index = 0
        play_single_file(audio_files[current_index])

def previous_music():
    global current_index
    if current_index > 0:
        current_index -= 1
        play_single_file(audio_files[current_index])
    else:
        current_index = len(audio_files) - 1
        play_single_file(audio_files[current_index])

def stop_music():
    pygame.mixer.music.stop()

def pause_music():
    pygame.mixer.music.pause()

def unpause_music():
    pygame.mixer.music.unpause()

def update_song_list():
    song_listbox.delete(0, tk.END)
    for i, file in enumerate(audio_files):
        song_listbox.insert(tk.END, f"{i + 1}. {os.path.basename(file)}")
    highlight_current_song()

def on_song_select(event):
    global current_index
    if len(song_listbox.curselection()) > 0:
        current_index = song_listbox.curselection()[0]
        play_single_file(audio_files[current_index])

def highlight_current_song():
    def highlight():
        for i in range(song_listbox.size()):
            if i == current_index:
                song_listbox.itemconfig(i, bg='yellow')
            else:
                song_listbox.itemconfig(i, bg='white')
    root.after(0, highlight)

def close_program():
    root.destroy()

# Add buttons to the Tkinter interface and arrange them horizontally
control_frame = tk.Frame(root)
control_frame.pack(pady=10)

play_button = tk.Button(control_frame, text="Play", command=play_music)
play_directory_button = tk.Button(control_frame, text="Play Directory", command=play_directory)
pause_button = tk.Button(control_frame, text="Pause", command=pause_music)
unpause_button = tk.Button(control_frame, text="Unpause", command=unpause_music)
stop_button = tk.Button(control_frame, text="Stop", command=stop_music)
next_button = tk.Button(control_frame, text="Next", command=next_music)
previous_button = tk.Button(control_frame, text="Previous", command=previous_music)
close_button = tk.Button(control_frame, text="Close", command=close_program)

play_button.grid(row=0, column=0, padx=5)
play_directory_button.grid(row=0, column=1, padx=5)
pause_button.grid(row=0, column=2, padx=5)
unpause_button.grid(row=0, column=3, padx=5)
stop_button.grid(row=0, column=4, padx=5)
next_button.grid(row=0, column=5, padx=5)
previous_button.grid(row=0, column=6, padx=5)
close_button.grid(row=0, column=7, padx=5)

# Create progress bar
progress_frame = tk.Frame(root)
progress_frame.pack(pady=10)

progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", length=400, mode="determinate")
progress_bar.pack()

# Create song list box
song_listbox = tk.Listbox(root, width=50, height=10)
song_listbox.pack(pady=10)
song_listbox.bind('<<ListboxSelect>>', on_song_select)

# Run the Tkinter application
root.mainloop()
