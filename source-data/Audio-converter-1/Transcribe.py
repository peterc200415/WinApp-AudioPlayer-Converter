import sys
import whisper
import ffmpeg

def transcribe_audio_to_srt(audio_path, srt_path):
    model = whisper.load_model("base")
    result = model.transcribe(audio_path)

    segments = result["segments"]
    with open(srt_path, "w") as srt_file:
        for i, segment in enumerate(segments):
            start = segment["start"]
            end = segment["end"]
            text = segment["text"]
            srt_file.write(f"{i + 1}\n")
            srt_file.write(f"{format_time(start)} --> {format_time(end)}\n")
            srt_file.write(f"{text}\n\n")

def format_time(seconds):
    millis = int((seconds % 1) * 1000)
    seconds = int(seconds)
    minutes = int(seconds // 60)
    seconds = seconds % 60
    hours = int(minutes // 60)
    minutes = minutes % 60
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"

if __name__ == "__main__":
    audio_path = sys.argv[1]
    srt_path = sys.argv[2]
    transcribe_audio_to_srt(audio_path, srt_path)
