# WinApp Audio Player Converter

A Windows-first desktop audio player with local Whisper transcription, subtitle caching, and assisted track identification / rename tools.

The app prefers a Qt UI built with `PySide6`, plays common audio formats through `pygame` + `pydub`, and can generate sidecar subtitles while you listen.

## Highlights

- Qt desktop UI with light / dark theme support
- Recursive folder playlist loading
- Playback support for `.mp3`, `.m4a`, `.wav`, `.wma`, `.flac`, `.aac`, `.ogg`, `.opus`, and `.mp4`
- Local Whisper transcription with `auto`, `cuda`, or `cpu` device selection
- Subtitle preview during playback, then background upgrade to fuller transcription
- Auto-save generated subtitles as `.auto.srt`
- Conservative `Identify & Rename` flow with preview before rename
- JSON config persisted at `config/settings.json`

## Requirements

- Python 3.10+
- FFmpeg available on `PATH`
- Windows is the primary supported desktop target

## Install

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Install FFmpeg if needed:

- Windows: add `C:\ffmpeg\bin` to `PATH`
- macOS: `brew install ffmpeg`
- Ubuntu / Debian: `sudo apt-get install ffmpeg`

## Run

Start the desktop app:

```bash
python main.py
```

Notes:

- The entrypoint prefers the Qt UI and falls back to the legacy UI only if the Qt import fails.
- When launched from a terminal, the process stays running while the GUI is open. That is expected.
- On Windows, if the window does not appear, check that PySide6 installed correctly and no Python exception was printed in the terminal.

## GPU And CUDA

The default config uses:

- `device = "auto"`
- `whisper_model = "base"`
- `subtitle_preview_model = "base"`

With `device = "auto"`, the app prefers CUDA when available and falls back to CPU when GPU execution is not usable.

The transcriber now handles these cases more safely:

- PyTorch CPU-only builds
- Unsupported GPU architecture for the installed PyTorch wheel
- Missing NVIDIA driver
- NVIDIA driver older than the CUDA runtime expected by PyTorch
- CUDA initialization and driver/runtime mismatch errors

If CUDA cannot be used, the app keeps transcription working by retrying on CPU instead of hard-failing model load.

## CUDA Troubleshooting

If GPU transcription is slower than expected or falls back to CPU:

1. Check the terminal output for warnings from `Transcriber`.
2. Verify that PyTorch is a CUDA build, not a `+cpu` build.
3. Verify that your NVIDIA driver is new enough for the installed PyTorch CUDA runtime.
4. If you have an older NVIDIA GPU, you may need a different PyTorch CUDA wheel instead of newer defaults.

Quick check:

```bash
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only')"
```

This repository also includes `fix_gpu_support.bat` as a helper for reinstalling a CUDA-enabled PyTorch build on Windows.

## Subtitle Output

Generated subtitles are saved next to the source audio file:

- Manual subtitles: `track.srt`
- Auto-generated subtitles: `track.auto.srt`

When both exist, the app prefers the manual `.srt` file.

## Identify And Rename

The `Identify & Rename` flow is intentionally conservative:

1. Read metadata and filename hints.
2. Search structured music metadata sources.
3. If that fails, transcribe sampled lyric snippets from multiple points in the song.
4. Search using lyric text and only keep results that are strong enough or repeated across samples.
5. Show a preview before any rename is applied.

This reduces accidental renames, but lyric-based matching is still probabilistic. Tracks with long instrumental sections, heavy effects, or poor transcription quality may still need manual review.

## Configuration

Configuration lives in `config/settings.json`.

Important keys:

- `whisper_model`
- `device`
- `whisper_language`
- `whisper_beam_size`
- `whisper_best_of`
- `theme`
- `auto_transcribe_on_play`
- `enable_subtitle_preview`
- `subtitle_preview_seconds`
- `subtitle_preview_model`
- `enable_full_transcription`
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

Run the focused test suite:

```bash
pytest -q -p no:cacheprovider
```

Relevant GPU fallback coverage now includes `tests/test_transcriber.py`.

## License

MIT
