"""Online track lookup and safe batch rename helpers."""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from html import unescape
from pathlib import Path
from typing import Optional
from urllib.parse import quote
from urllib.request import Request, urlopen


INVALID_FILENAME_CHARS = r'<>:"/\|?*'
CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
MOJIBAKE_PATTERN = re.compile(r"[<>\[\]{}^~`|¦¥¼½¾©®°±µ·×÷]")
NOISE_PATTERNS = [
    r"\[[^\]]*\]",
    r"\([^)]+\)",
    r"\{[^}]+\}",
    r"\b(?:official|lyrics?|audio|video|mv|pv|ver\.?|version|live|remaster(?:ed)?|hq|hd)\b",
    r"\b(?:feat\.?|ft\.?|featuring)\b.*$",
]


@dataclass
class TrackInfo:
    path: str
    file_name: str
    title: str = ""
    artist: str = ""
    album: str = ""
    duration_seconds: float = 0.0


@dataclass
class TrackMatch:
    source: str
    title: str
    artist: str
    release: str
    score: int
    suggested_name: str
    reason: str


@dataclass
class RenamePreview:
    path: str
    current_name: str
    detected_query: str
    match: Optional[TrackMatch]
    error: str = ""


class TrackRenameService:
    """Resolve likely song metadata online and rename files safely."""

    API_ROOT = "https://musicbrainz.org/ws/2/recording"
    SEARCH_ROOT = "https://html.duckduckgo.com/html/"
    USER_AGENT = "WinAppAudioStudio/1.0 (desktop app rename assistant)"
    LYRICS_HINTS = (
        "lyrics",
        "\u52d5\u614b\u6b4c\u8a5e",
        "\u52a8\u6001\u6b4c\u8bcd",
        "\u6b4c\u8a5e",
        "\u6b4c\u8bcd",
        "\u52d5\u614b",
        "\u52a8\u6001",
    )

    def __init__(self) -> None:
        self._last_lookup_at = 0.0

    def build_preview(self, path: str) -> RenamePreview:
        info = self.read_track_info(path)
        detected_query = self._build_query_text(info)
        if not detected_query:
            return RenamePreview(
                path=path,
                current_name=Path(path).name,
                detected_query="",
                match=None,
                error="Could not derive a usable query from filename or metadata.",
            )

        try:
            match = self.lookup_track(info)
        except Exception as exc:
            return RenamePreview(
                path=path,
                current_name=Path(path).name,
                detected_query=detected_query,
                match=None,
                error=str(exc),
            )

        if match is None:
            return RenamePreview(
                path=path,
                current_name=Path(path).name,
                detected_query=detected_query,
                match=None,
                error="No confident source match found.",
            )

        return RenamePreview(
            path=path,
            current_name=Path(path).name,
            detected_query=detected_query,
            match=match,
        )

    def build_preview_from_lyrics(self, path: str, lyric_snippet: str) -> RenamePreview:
        cleaned_snippet = self._clean_search_text(lyric_snippet)
        if not cleaned_snippet:
            return RenamePreview(
                path=path,
                current_name=Path(path).name,
                detected_query="",
                match=None,
                error="No usable subtitle text for lyric matching.",
            )

        try:
            match = self.lookup_track_from_lyrics(path, cleaned_snippet)
        except Exception as exc:
            return RenamePreview(
                path=path,
                current_name=Path(path).name,
                detected_query=cleaned_snippet,
                match=None,
                error=str(exc),
            )

        if match is None:
            return RenamePreview(
                path=path,
                current_name=Path(path).name,
                detected_query=cleaned_snippet,
                match=None,
                error="No confident subtitle-based match found.",
            )

        return RenamePreview(
            path=path,
            current_name=Path(path).name,
            detected_query=cleaned_snippet,
            match=match,
        )

    def build_preview_from_lyric_snippets(self, path: str, lyric_snippets: list[str]) -> RenamePreview:
        cleaned_snippets = [self._clean_search_text(snippet) for snippet in lyric_snippets]
        cleaned_snippets = [snippet for snippet in cleaned_snippets if snippet]
        if not cleaned_snippets:
            return RenamePreview(
                path=path,
                current_name=Path(path).name,
                detected_query="",
                match=None,
                error="No usable subtitle text for fallback.",
            )

        previews = [self.build_preview_from_lyrics(path, snippet) for snippet in cleaned_snippets]
        matched_previews = [preview for preview in previews if preview.match is not None]
        if not matched_previews:
            return RenamePreview(
                path=path,
                current_name=Path(path).name,
                detected_query=" | ".join(cleaned_snippets[:2]),
                match=None,
                error="No confident subtitle-based match found across sampled lyric snippets.",
            )

        chosen = self._choose_best_lyric_preview(matched_previews)
        if chosen is None:
            return RenamePreview(
                path=path,
                current_name=Path(path).name,
                detected_query=" | ".join(cleaned_snippets[:2]),
                match=None,
                error="Sampled lyric snippets disagreed on the likely song.",
            )

        snippet_summary = self._clean_search_text(" | ".join(cleaned_snippets[:2]))
        return RenamePreview(
            path=path,
            current_name=Path(path).name,
            detected_query=snippet_summary,
            match=chosen.match,
            error=chosen.error,
        )

    def apply_rename(self, preview: RenamePreview) -> str:
        if preview.match is None:
            raise ValueError("No match available for rename.")

        source_path = Path(preview.path)
        target_path = source_path.with_name(preview.match.suggested_name)

        if target_path == source_path:
            return str(source_path)
        if target_path.exists():
            raise FileExistsError(f"Target file already exists: {target_path.name}")

        source_path.rename(target_path)
        return str(target_path)

    def read_track_info(self, path: str) -> TrackInfo:
        file_path = Path(path)
        info = TrackInfo(path=str(file_path), file_name=file_path.name)

        metadata = self._read_ffprobe_tags(file_path)
        format_section = metadata.get("format", {}) if isinstance(metadata, dict) else {}
        tags = format_section.get("tags", {}) if isinstance(format_section, dict) else {}

        info.title = self._sanitize_metadata_value(self._first_non_empty(tags.get("title"), tags.get("TITLE")))
        info.artist = self._sanitize_metadata_value(
            self._first_non_empty(
                tags.get("artist"),
                tags.get("ARTIST"),
                tags.get("album_artist"),
                tags.get("ALBUM_ARTIST"),
            )
        )
        info.album = self._sanitize_metadata_value(self._first_non_empty(tags.get("album"), tags.get("ALBUM")))

        try:
            info.duration_seconds = float(format_section.get("duration", 0.0) or 0.0)
        except (TypeError, ValueError):
            info.duration_seconds = 0.0

        if not info.title or not info.artist:
            guessed_artist, guessed_title = self._parse_filename(file_path.stem)
            info.artist = info.artist or guessed_artist
            info.title = info.title or guessed_title

        return info

    def lookup_track(self, info: TrackInfo) -> Optional[TrackMatch]:
        candidates: list[TrackMatch] = []
        seen: set[tuple[str, str, str]] = set()

        for query in self._build_search_queries(info):
            for recording in self._search_recordings(query):
                title = self._clean_search_text(str(recording.get("title", "")).strip())
                artist = self._join_artist_credit(recording.get("artist-credit", []))
                releases = recording.get("releases", [])
                release = self._clean_search_text(str(releases[0].get("title", "")).strip()) if releases else ""
                raw_score = int(recording.get("score", 0) or 0)
                raw_length_ms = int(recording.get("length", 0) or 0)

                if not title or not artist:
                    continue

                key = (title.casefold(), artist.casefold(), release.casefold())
                if key in seen:
                    continue
                seen.add(key)

                weighted_score = self._score_candidate(
                    info,
                    title=title,
                    artist=artist,
                    release=release,
                    raw_score=raw_score,
                    raw_length_ms=raw_length_ms,
                )
                if weighted_score < 72:
                    continue

                candidates.append(
                    TrackMatch(
                        source="MusicBrainz",
                        title=title,
                        artist=artist,
                        release=release,
                        score=weighted_score,
                        suggested_name=self._build_filename(artist, title, release, Path(info.path).suffix),
                        reason=f"MusicBrainz score {raw_score}, weighted {weighted_score}",
                    )
                )

        if not candidates:
            return None

        candidates.sort(key=lambda match: match.score, reverse=True)
        return candidates[0]

    def lookup_track_from_lyrics(self, path: str, lyric_snippet: str) -> Optional[TrackMatch]:
        lyric_query = self._build_lyric_query(lyric_snippet)
        if not lyric_query:
            return None

        for title_text in self._search_web_titles(lyric_query):
            candidate_info = self._track_info_from_search_title(path, title_text)
            if candidate_info is None:
                continue
            match = self.lookup_track(candidate_info)
            if match is not None:
                match.reason = f"{match.reason}; subtitle snippet fallback"
                return match
        return None

    def _read_ffprobe_tags(self, path: Path) -> dict:
        try:
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                str(path),
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=8,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return {}
            payload = json.loads(result.stdout)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _build_search_queries(self, info: TrackInfo) -> list[str]:
        title = self._normalize_token(info.title)
        artist = self._normalize_token(info.artist)
        album = self._normalize_token(info.album)
        queries: list[str] = []

        def add_query(*parts: str) -> None:
            query = " AND ".join(part for part in parts if part)
            if query and query not in queries:
                queries.append(query)

        if title and artist:
            add_query(f'recording:"{title}"', f'artist:"{artist}"')
        if title and artist and album:
            add_query(f'recording:"{title}"', f'artist:"{artist}"', f'release:"{album}"')

        clean_title = self._clean_search_text(title)
        clean_artist = self._clean_search_text(artist)
        if clean_title and clean_artist and (clean_title != title or clean_artist != artist):
            add_query(f'recording:"{clean_title}"', f'artist:"{clean_artist}"')

        if clean_title:
            add_query(f'recording:"{clean_title}"')
        if title:
            add_query(f'recording:"{title}"')

        fallback = self._normalize_token(self._build_query_text(info))
        clean_fallback = self._clean_search_text(fallback)
        if clean_fallback:
            add_query(f'"{clean_fallback}"')
        if fallback and fallback != clean_fallback:
            add_query(f'"{fallback}"')

        return queries

    def _build_query_text(self, info: TrackInfo) -> str:
        pieces = [piece for piece in [info.artist.strip(), info.title.strip(), info.album.strip()] if piece]
        if pieces:
            return " - ".join(pieces[:2]) if len(pieces) >= 2 else pieces[0]
        return self._clean_search_text(Path(info.file_name).stem)

    def _parse_filename(self, stem: str) -> tuple[str, str]:
        cleaned = self._clean_search_text(stem)
        for delimiter in (" - ", " – ", " — ", "_-_", " / ", " ~ ", "／", "｜"):
            if delimiter in cleaned:
                left, right = cleaned.split(delimiter, 1)
                return self._normalize_token(left), self._normalize_token(right)
        return "", cleaned

    def _build_lyric_query(self, lyric_snippet: str) -> str:
        cleaned = self._clean_search_text(lyric_snippet)
        if not cleaned:
            return ""

        if self._contains_cjk(cleaned):
            compact = re.sub(r"[^\u3400-\u4dbf\u4e00-\u9fffA-Za-z0-9]", "", cleaned)
            if len(compact) < 4:
                return ""
            return f'"{compact[:11]}" \u6b4c\u8a5e'

        tokens = [token for token in cleaned.split() if len(token) > 1]
        if not tokens:
            return ""
        snippet = " ".join(tokens[:8]).strip()
        return f'"{snippet}" lyrics'

    def _search_recordings(self, query: str) -> list[dict]:
        if not query:
            return []

        self._rate_limit()
        url = f"{self.API_ROOT}?query={quote(query)}&fmt=json&limit=5"
        request = Request(url, headers={"User-Agent": self.USER_AGENT})
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        recordings = payload.get("recordings", [])
        return recordings if isinstance(recordings, list) else []

    def _search_web_titles(self, query: str) -> list[str]:
        self._rate_limit()
        url = f"{self.SEARCH_ROOT}?q={quote(query)}"
        request = Request(url, headers={"User-Agent": self.USER_AGENT})
        with urlopen(request, timeout=10) as response:
            html = response.read().decode("utf-8", errors="ignore")

        titles: list[str] = []
        for raw_title in re.findall(
            r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*>(.*?)</a>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            title = unescape(re.sub(r"<[^>]+>", " ", raw_title))
            title = re.sub(r"\s+", " ", title).strip()
            if title and title not in titles:
                titles.append(title)
        return titles[:8]

    def _track_info_from_search_title(self, path: str, title_text: str) -> Optional[TrackInfo]:
        cleaned = re.sub(r"\s*\|\s*.*$", "", title_text).strip()
        cleaned = re.sub(
            r"\s*[-|]\s*(Genius Lyrics|Musixmatch|AZLyrics|Lyrics\.com|\u6b4c\u8a5e|\u6b4c\u8bcd|\u52d5\u614b\u6b4c\u8a5e|\u52a8\u6001\u6b4c\u8bcd).*?$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = self._strip_lyric_hints(cleaned)
        cleaned = self._clean_search_text(cleaned)
        if not cleaned:
            return None

        artist = ""
        title = cleaned
        for delimiter in (" - ", " – ", " — ", " by ", "／", "｜"):
            if delimiter in cleaned:
                left, right = cleaned.split(delimiter, 1)
                if delimiter == " by ":
                    title, artist = left.strip(), right.strip()
                else:
                    artist, title = left.strip(), right.strip()
                break

        if not artist:
            parsed_title, parsed_artist = self._parse_quoted_song_title(cleaned)
            title = parsed_title or title
            artist = parsed_artist or artist

        title = self._clean_search_text(self._strip_lyric_hints(title))
        artist = self._clean_search_text(self._strip_lyric_hints(artist))
        if not title:
            return None

        return TrackInfo(path=path, file_name=Path(path).name, title=title, artist=artist)

    def _score_candidate(
        self,
        info: TrackInfo,
        title: str,
        artist: str,
        release: str,
        raw_score: int,
        raw_length_ms: int,
    ) -> int:
        score = float(raw_score)
        title_ratio = self._similarity(info.title, title)
        artist_ratio = self._similarity(info.artist, artist)
        release_ratio = self._similarity(info.album, release)

        score += title_ratio * 20.0
        score += artist_ratio * 12.0
        score += release_ratio * 4.0

        if info.title and title_ratio < 0.55:
            score -= 15.0
        if info.artist and artist_ratio < 0.45:
            score -= 12.0

        if info.duration_seconds > 0 and raw_length_ms > 0:
            duration_delta = abs((raw_length_ms / 1000.0) - info.duration_seconds)
            if duration_delta <= 3:
                score += 6.0
            elif duration_delta <= 8:
                score += 3.0
            elif duration_delta >= 20:
                score -= 8.0

        return int(round(score))

    def _join_artist_credit(self, credits: list[dict]) -> str:
        parts: list[str] = []
        for credit in credits:
            if isinstance(credit, str):
                parts.append(credit)
            elif isinstance(credit, dict):
                name = credit.get("name")
                if name:
                    parts.append(str(name))
        return self._clean_search_text("".join(parts).strip())

    def _build_filename(self, artist: str, title: str, release: str, suffix: str) -> str:
        base = f"{artist} - {title}".strip()
        if release:
            base = f"{base} [{release}]"
        return f"{self._sanitize_filename(base)}{suffix}"

    def _sanitize_filename(self, value: str) -> str:
        sanitized = "".join("_" if char in INVALID_FILENAME_CHARS else char for char in value)
        sanitized = re.sub(r"\s+", " ", sanitized).strip(" .")
        return sanitized or "Unknown Track"

    def _normalize_token(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    def _sanitize_metadata_value(self, value: str) -> str:
        cleaned = self._clean_search_text(value)
        if self._is_likely_mojibake(cleaned):
            return ""
        return cleaned

    def _choose_best_lyric_preview(self, previews: list[RenamePreview]) -> Optional[RenamePreview]:
        groups: dict[tuple[str, str], list[RenamePreview]] = {}
        for preview in previews:
            if preview.match is None:
                continue
            key = (
                preview.match.title.casefold(),
                preview.match.artist.casefold(),
            )
            groups.setdefault(key, []).append(preview)

        if not groups:
            return None

        ranked_groups = sorted(
            groups.values(),
            key=lambda group: (
                len(group),
                max(item.match.score for item in group if item.match is not None),
                sum(item.match.score for item in group if item.match is not None),
            ),
            reverse=True,
        )

        best_group = ranked_groups[0]
        best_preview = max(best_group, key=lambda item: item.match.score if item.match else 0)

        if len(best_group) >= 2:
            consensus = len(best_group)
            best_preview.match.reason = f"{best_preview.match.reason}; lyric consensus {consensus}"
            return best_preview

        if best_preview.match.score >= 92:
            best_preview.match.reason = f"{best_preview.match.reason}; strong single lyric hit"
            return best_preview

        return None

    def _clean_search_text(self, value: str) -> str:
        cleaned = value or ""
        cleaned = cleaned.replace("_", " ")
        for pattern in NOISE_PATTERNS:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b\d{3,4}p\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"[|]+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_.")
        return cleaned

    def _contains_cjk(self, value: str) -> bool:
        return bool(CJK_PATTERN.search(value))

    def _parse_quoted_song_title(self, value: str) -> tuple[str, str]:
        for pattern in (
            r"\u300a([^\u300b]+)\u300b",
            r"\u3008([^\u3009]+)\u3009",
            r"\u300c([^\u300d]+)\u300d",
            r"\u300e([^\u300f]+)\u300f",
        ):
            match = re.search(pattern, value)
            if not match:
                continue
            title = match.group(1).strip()
            artist = self._clean_search_text(self._strip_lyric_hints(value.replace(match.group(0), " ")))
            return title, artist
        return "", ""

    def _strip_lyric_hints(self, value: str) -> str:
        cleaned = value
        for hint in self.LYRICS_HINTS:
            cleaned = re.sub(rf"\s*{re.escape(hint)}\s*", " ", cleaned, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", cleaned).strip()

    def _is_likely_mojibake(self, value: str) -> bool:
        if not value:
            return False
        if self._contains_cjk(value):
            return False
        compact = re.sub(r"\s+", "", value)
        if len(compact) < 3:
            return False
        suspicious_count = len(MOJIBAKE_PATTERN.findall(compact))
        suspicious_sequences = ("Ã", "Â", "Ð", "Ñ", "¤", "¥", "¼", "½", "¾")
        if any(sequence in compact for sequence in suspicious_sequences):
            return True
        return suspicious_count >= max(2, len(compact) // 3)

    def _similarity(self, left: str, right: str) -> float:
        if not left or not right:
            return 0.0
        return SequenceMatcher(None, left.casefold(), right.casefold()).ratio()

    def _rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_lookup_at
        if elapsed < 1.05:
            time.sleep(1.05 - elapsed)
        self._last_lookup_at = time.monotonic()

    @staticmethod
    def _first_non_empty(*values: object) -> str:
        for value in values:
            text = str(value).strip() if value is not None else ""
            if text:
                return text
        return ""
