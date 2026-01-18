import pygame
import tkinter as tk
from tkinter import filedialog, scrolledtext
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
def update_subtitles(subtitles):
    while pygame.mixer.music.get_busy():
        current_time = pygame.mixer.music.get_pos() // 1000
        for start, end, text in subtitles:
            if start <= current_time <= end:
                text_area.delete(1.0, tk.END)
                text_area.insert(tk.END, text)
                break
        time.sleep(0.5)

# Define functions to control the music player
def play_music():
    file_path = filedialog.askopenfilename(filetypes=[("Audio Files", "*.mp3 *.m4a")])
    if file_path:
        # Look for a .srt file with the same name and display its contents
        srt_file_path = os.path.splitext(file_path)[0] + ".srt"
        subtitles = []
        if os.path.exists(srt_file_path):
            subtitles = parse_srt(srt_file_path)
        else:
            text_area.delete(1.0, tk.END)
            text_area.insert(tk.END, "No associated .srt file found.")

        # Play the audio file
        if file_path.endswith('.mp3'):
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            if subtitles:
                threading.Thread(target=update_subtitles, args=(subtitles,)).start()
        elif file_path.endswith('.m4a'):
            play_m4a(file_path, subtitles)

def play_m4a(file_path, subtitles):
    audio = AudioSegment.from_file(file_path)
    temp_wav_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_wav_file.close()  # Close the file so that it can be used by other processes
    audio.export(temp_wav_file.name, format="wav")
    if os.path.exists(temp_wav_file.name):
        pygame.mixer.music.load(temp_wav_file.name)
        pygame.mixer.music.play()
        if subtitles:
            threading.Thread(target=update_subtitles, args=(subtitles,)).start()
        # Delete the temporary file after playback is complete
        def cleanup():
            pygame.mixer.music.set_endevent(pygame.USEREVENT)
            while pygame.mixer.music.get_busy():
                pygame.time.wait(100)
            pygame.mixer.music.stop()  # Stop audio playback
            os.remove(temp_wav_file.name)
        threading.Thread(target=cleanup).start()
    else:
        print(f"Failed to create temporary file: {temp_wav_file.name}")

def stop_music():
    pygame.mixer.music.stop()

def pause_music():
    pygame.mixer.music.pause()

def unpause_music():
    pygame.mixer.music.unpause()

# Add buttons to the Tkinter interface and arrange them horizontally
play_button = tk.Button(root, text="Play", command=play_music)
pause_button = tk.Button(root, text="Pause", command=pause_music)
unpause_button = tk.Button(root, text="Unpause", command=unpause_music)
stop_button = tk.Button(root, text="Stop", command=stop_music)

play_button.pack(side=tk.LEFT, padx=15)
pause_button.pack(side=tk.LEFT, padx=15)
unpause_button.pack(side=tk.LEFT, padx=15)
stop_button.pack(side=tk.LEFT, padx=15)

# Run the Tkinter application
root.mainloop()
