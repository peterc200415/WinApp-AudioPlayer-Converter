"""JSON-backed application configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Config:
    """Simple configuration wrapper with stable defaults."""

    DEFAULT_SUPPORTED_FORMATS = [
        ".mp3",
        ".m4a",
        ".wav",
        ".wma",
        ".flac",
        ".aac",
        ".ogg",
        ".opus",
        ".mp4",
    ]

    DEFAULT_CONFIG = {
        "whisper_model": "base",
        "device": "auto",
        "whisper_language": "auto",
        "whisper_beam_size": 1,
        "whisper_best_of": 1,
        "translation_target": "zh-TW",
        "font_size": 15,
        "subtitle_font_size": 14,
        "theme": "light",
        "auto_transcribe": False,
        "auto_transcribe_on_play": True,
        "enable_subtitle_preview": True,
        "subtitle_preview_seconds": 20,
        "subtitle_preview_model": "base",
        "enable_full_transcription": True,
        "subtitle_chunk_lead_seconds": 12,
        "base_chunk_seconds": 45,
        "upgrade_start_after_seconds": 60,
        "supported_formats": DEFAULT_SUPPORTED_FORMATS,
    }

    def __init__(self, config_path: str = "config/settings.json"):
        self.config_path = Path(config_path)
        self._config = self.DEFAULT_CONFIG.copy()
        self.load()

    def load(self) -> None:
        """Load config from disk, preserving defaults for missing keys."""
        if self.config_path.exists():
            try:
                with self.config_path.open("r", encoding="utf-8") as file:
                    loaded_config = json.load(file)
            except (json.JSONDecodeError, OSError) as exc:
                print(f"Failed to load config: {exc}")
            else:
                if isinstance(loaded_config, dict):
                    self._config.update(loaded_config)
                    self._normalize_supported_formats()
                return

        self.save()

    def save(self) -> None:
        """Persist config to disk."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.config_path.open("w", encoding="utf-8") as file:
                json.dump(self._config, file, indent=4, ensure_ascii=False)
        except OSError as exc:
            print(f"Failed to save config: {exc}")

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._config[key] = value

    def get_all(self) -> dict[str, Any]:
        return self._config.copy()

    def _normalize_supported_formats(self) -> None:
        configured = self._config.get("supported_formats", [])
        if not isinstance(configured, list):
            self._config["supported_formats"] = list(self.DEFAULT_SUPPORTED_FORMATS)
            return

        normalized: list[str] = []
        seen: set[str] = set()
        for ext in configured + self.DEFAULT_SUPPORTED_FORMATS:
            if not isinstance(ext, str):
                continue
            ext_text = ext.strip().lower()
            if not ext_text:
                continue
            if not ext_text.startswith("."):
                ext_text = f".{ext_text}"
            if ext_text in seen:
                continue
            seen.add(ext_text)
            normalized.append(ext_text)
        self._config["supported_formats"] = normalized
