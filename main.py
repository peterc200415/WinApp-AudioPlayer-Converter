"""
應用程式主入口
從專案根目錄運行：python main.py
"""

import os
from pathlib import Path
 

# Reduce console noise on startup
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")



def _ensure_ffmpeg_on_path() -> None:
    """Ensure FFmpeg is discoverable by pydub on Windows."""
    if os.name != "nt":
        return

    ffmpeg_bin = Path(r"C:\ffmpeg\bin")
    if not (ffmpeg_bin / "ffmpeg.exe").exists():
        return

    current_path = os.environ.get("PATH", "")
    if str(ffmpeg_bin) not in current_path:
        os.environ["PATH"] = f"{ffmpeg_bin};{current_path}" if current_path else str(ffmpeg_bin)


_ensure_ffmpeg_on_path()

try:
    from src.ui_qt.main_window import MainWindow
except Exception:
    from src.ui.main_window import MainWindow


def main():
    """主函數"""
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
