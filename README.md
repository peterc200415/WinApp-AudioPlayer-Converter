# WinApp Audio Player Converter

A desktop audio player with on-device Whisper transcription, subtitle caching, and assisted track identification / rename tools.

The project currently uses a Qt desktop UI built with `PySide6`, plays common audio formats through `pygame` + `pydub`, and can generate `.auto.srt` subtitles while you listen.

## Current Features

- Qt desktop UI with light / dark mode toggle
- Folder-based playlist loading with recursive audio file discovery
- Playback support for `.mp3`, `.m4a`, `.wav`, `.wma`, `.flac`, `.aac`, `.ogg`, `.opus`, and `.mp4`
- On-device Whisper transcription with GPU support when CUDA is available
- Subtitle preview while playing, plus background upgrade to fuller transcription
- Auto-save generated subtitles as sidecar `.auto.srt` files
- Track source lookup and safe rename preview
- Metadata / filename lookup first, then lyric-based fallback from sampled subtitle snippets
- Multi-sample lyric matching to reduce false positives on songs with long intros or noisy early lyrics
- Config persisted in `config/settings.json`

## Requirements

- Python 3.10+
- FFmpeg available on `PATH`
- Windows is the primary target environment for the current app flow

## Install

```bash
pip install -r requirements.txt
```

Install FFmpeg if it is not already available:

- Windows: add `C:\ffmpeg\bin` to `PATH`
- macOS: `brew install ffmpeg`
- Ubuntu / Debian: `sudo apt-get install ffmpeg`

## Run

```bash
python main.py
```

The entrypoint prefers the Qt UI and falls back to the legacy UI only if the Qt import fails.

## GPU Notes

- Set `device` to `auto` to prefer CUDA when available
- Whisper will fall back to CPU if the installed PyTorch build does not support your GPU architecture
- On older NVIDIA cards, using a matching CUDA wheel for PyTorch matters more than changing app code

## Subtitle Output

Generated subtitles are saved next to the source audio file:

- Manual subtitles: `track.srt`
- Auto-generated subtitles: `track.auto.srt`

The app prefers manual `.srt` files when both exist.

## Identify And Rename

The `Identify & Rename` flow is intentionally conservative:

1. Read metadata and filename hints
2. Search structured music metadata sources
3. If that fails, transcribe sampled lyric snippets from multiple points in the song
4. Search using lyric text and only keep results that are strong enough or repeated across samples
5. Show a preview before any rename is applied

This reduces accidental renames, but lyric-based matching is still probabilistic. Songs with long instrumental sections, heavy effects, or poor transcription quality may still need manual review.

## Settings

Configuration is stored in `config/settings.json`.

Common keys:

- `whisper_model`
- `device`
- `whisper_language`
- `whisper_beam_size`
- `whisper_best_of`
- `subtitle_font_size`
- `theme`
- `auto_transcribe_on_play`
- `enable_full_transcription`
- `subtitle_preview_seconds`
- `subtitle_chunk_lead_seconds`
- `base_chunk_seconds`
- `upgrade_start_after_seconds`
- `supported_formats`

## Project Layout

```text
src/
  core/
    audio_player.py
    subtitle_parser.py
    track_rename_service.py
    transcriber.py
    transcription_manager.py
  ui/
    ... legacy UI
  ui_qt/
    main_window.py
  utils/
    config.py
    file_utils.py
    time_utils.py

tests/
main.py
requirements.txt
```

## Testing

```bash
pytest -q -p no:cacheprovider
```

## License

MIT
