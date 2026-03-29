import json

from src.core.track_rename_service import RenamePreview, TrackInfo, TrackMatch, TrackRenameService


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_read_track_info_falls_back_to_filename(monkeypatch, tmp_path):
    service = TrackRenameService()
    track = tmp_path / "Artist Name - Song Title.mp3"
    track.write_text("x", encoding="utf-8")

    monkeypatch.setattr(service, "_read_ffprobe_tags", lambda _path: {})

    info = service.read_track_info(str(track))

    assert info.artist == "Artist Name"
    assert info.title == "Song Title"


def test_read_track_info_discards_mojibake_metadata(monkeypatch, tmp_path):
    service = TrackRenameService()
    track = tmp_path / "amimi01.mp3"
    track.write_text("x", encoding="utf-8")

    monkeypatch.setattr(
        service,
        "_read_ffprobe_tags",
        lambda _path: {
            "format": {
                "tags": {
                    "artist": "<\u00a5\u00bc\u00aa\u00be->",
                }
            }
        },
    )

    info = service.read_track_info(str(track))

    assert info.artist == ""
    assert info.title == "amimi01"


def test_lookup_track_builds_suggested_filename(monkeypatch):
    service = TrackRenameService()

    payload = {
        "recordings": [
            {
                "title": "Song Title",
                "score": 95,
                "artist-credit": [{"name": "Artist Name"}],
                "releases": [{"title": "Album Name"}],
            }
        ]
    }

    monkeypatch.setattr("src.core.track_rename_service.urlopen", lambda *_args, **_kwargs: FakeResponse(payload))
    monkeypatch.setattr(service, "_rate_limit", lambda: None)

    match = service.lookup_track(
        TrackInfo(
            path="track.mp3",
            file_name="track.mp3",
            title="Song Title",
            artist="Artist Name",
        )
    )

    assert match is not None
    assert match.source == "MusicBrainz"
    assert match.suggested_name == "Artist Name - Song Title [Album Name].mp3"


def test_read_track_info_cleans_common_noise(monkeypatch, tmp_path):
    service = TrackRenameService()
    track = tmp_path / "Artist Name - Song Title (Official Video) feat. Guest [HD].mp3"
    track.write_text("x", encoding="utf-8")

    monkeypatch.setattr(service, "_read_ffprobe_tags", lambda _path: {})

    info = service.read_track_info(str(track))

    assert info.artist == "Artist Name"
    assert info.title == "Song Title"


def test_lookup_track_prefers_better_similarity_over_first_result(monkeypatch):
    service = TrackRenameService()
    monkeypatch.setattr(
        service,
        "_search_recordings",
        lambda _query: [
            {
                "title": "Wrong Song",
                "score": 92,
                "artist-credit": [{"name": "Other Artist"}],
                "releases": [{"title": "Other Album"}],
                "length": 180000,
            },
            {
                "title": "Song Title",
                "score": 88,
                "artist-credit": [{"name": "Artist Name"}],
                "releases": [{"title": "Album Name"}],
                "length": 181000,
            },
        ],
    )

    match = service.lookup_track(
        TrackInfo(
            path="track.mp3",
            file_name="track.mp3",
            title="Song Title",
            artist="Artist Name",
            duration_seconds=181.2,
        )
    )

    assert match is not None
    assert match.title == "Song Title"
    assert match.artist == "Artist Name"


def test_track_info_from_search_title_parses_artist_and_title():
    service = TrackRenameService()

    info = service._track_info_from_search_title(
        "track.mp3",
        "Artist Name - Song Title Lyrics | Genius Lyrics",
    )

    assert info is not None
    assert info.artist == "Artist Name"
    assert info.title == "Song Title"


def test_build_preview_from_lyrics_uses_fallback_match(monkeypatch):
    service = TrackRenameService()
    original_lookup_track = service.lookup_track

    monkeypatch.setattr(
        service,
        "_search_web_titles",
        lambda _query: ["Artist Name - Song Title Lyrics | Genius Lyrics"],
    )
    monkeypatch.setattr(
        service,
        "lookup_track",
        lambda info: original_lookup_track(
            TrackInfo(
                path=info.path,
                file_name=info.file_name,
                title="Song Title",
                artist="Artist Name",
            )
        ),
    )

    def fake_search_recordings(_query):
        return [
            {
                "title": "Song Title",
                "score": 90,
                "artist-credit": [{"name": "Artist Name"}],
                "releases": [{"title": "Album Name"}],
                "length": 180000,
            }
        ]

    monkeypatch.setattr(service, "_search_recordings", fake_search_recordings)

    preview = service.build_preview_from_lyrics("track.mp3", "some subtitle snippet here")

    assert preview.match is not None
    assert preview.match.title == "Song Title"


def test_build_lyric_query_prefers_chinese_lyrics_keyword():
    service = TrackRenameService()

    query = service._build_lyric_query(
        "\u6211\u66fe\u7d93\u8de8\u904e\u5c71\u548c\u5927\u6d77 \u4e5f\u7a7f\u904e\u4eba\u5c71\u4eba\u6d77"
    )

    assert query == '"\u6211\u66fe\u7d93\u8de8\u904e\u5c71\u548c\u5927\u6d77\u4e5f\u7a7f" \u6b4c\u8a5e'


def test_track_info_from_search_title_parses_chinese_delimiters():
    service = TrackRenameService()

    info = service._track_info_from_search_title(
        "track.mp3",
        "\u4e94\u6708\u5929\uff5c\u5014\u5f37 \u6b4c\u8a5e",
    )

    assert info is not None
    assert info.artist == "\u4e94\u6708\u5929"
    assert info.title == "\u5014\u5f37"


def test_track_info_from_search_title_parses_quoted_chinese_title():
    service = TrackRenameService()

    info = service._track_info_from_search_title(
        "track.mp3",
        "\u4e94\u6708\u5929\u300a\u5014\u5f37\u300b\u52d5\u614b\u6b4c\u8a5e",
    )

    assert info is not None
    assert info.artist == "\u4e94\u6708\u5929"
    assert info.title == "\u5014\u5f37"


def test_build_preview_from_lyric_snippets_prefers_consensus(monkeypatch):
    service = TrackRenameService()

    monkeypatch.setattr(
        service,
        "build_preview_from_lyrics",
        lambda path, snippet: {
            "first line": RenamePreview(
                path=path,
                current_name="track.mp3",
                detected_query=snippet,
                match=TrackMatch(
                    source="MusicBrainz",
                    title="Song A",
                    artist="Artist A",
                    release="Album",
                    score=96,
                    suggested_name="Artist A - Song A [Album].mp3",
                    reason="mock",
                ),
            ),
            "second line": RenamePreview(
                path=path,
                current_name="track.mp3",
                detected_query=snippet,
                match=TrackMatch(
                    source="MusicBrainz",
                    title="Song A",
                    artist="Artist A",
                    release="Album",
                    score=94,
                    suggested_name="Artist A - Song A [Album].mp3",
                    reason="mock",
                ),
            ),
            "third line": RenamePreview(
                path=path,
                current_name="track.mp3",
                detected_query=snippet,
                match=TrackMatch(
                    source="MusicBrainz",
                    title="Song B",
                    artist="Artist B",
                    release="Album",
                    score=90,
                    suggested_name="Artist B - Song B [Album].mp3",
                    reason="mock",
                ),
            ),
        }[snippet],
    )

    preview = service.build_preview_from_lyric_snippets("track.mp3", ["first line", "second line", "third line"])

    assert preview.match is not None
    assert preview.match.title == "Song A"
    assert "consensus" in preview.match.reason


def test_build_preview_from_lyric_snippets_rejects_weak_single_hit(monkeypatch):
    service = TrackRenameService()

    monkeypatch.setattr(
        service,
        "build_preview_from_lyrics",
        lambda path, snippet: RenamePreview(
            path=path,
            current_name="track.mp3",
            detected_query=snippet,
            match=TrackMatch(
                source="MusicBrainz",
                title="Song A",
                artist="Artist A",
                release="Album",
                score=85,
                suggested_name="Artist A - Song A [Album].mp3",
                reason="mock",
            )
            if snippet == "only hit"
            else None,
            error="" if snippet == "only hit" else "no match",
        ),
    )

    preview = service.build_preview_from_lyric_snippets("track.mp3", ["only hit", "miss one", "miss two"])

    assert preview.match is None
    assert "disagreed" in preview.error
