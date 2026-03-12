from types import SimpleNamespace

from jmoona import app


def _base_config():
    return {
        "lang": ["fr", "en"],
        "sub_lang": "fr",
        "use_fzf": False,
    }


def test_resolve_playback_preferences_respects_sub_off():
    prefs = app._resolve_playback_preferences(
        {"original_language": "ja"},
        SimpleNamespace(lang="fr", sub="off"),
        _base_config(),
    )

    assert prefs["audio_preferences"][:3] == ["fr", "ja", "en"]
    assert prefs["subtitle_language"] is None
    assert prefs["subtitle_behavior"] == "never"


def test_prepare_playback_uses_embedded_french_subtitles(monkeypatch):
    monkeypatch.setattr(
        app,
        "detect_tracks",
        lambda _: {
            "audio": [
                {"lang": "en", "mpv_id": 2},
                {"lang": "ja", "mpv_id": 3},
            ],
            "subs": [
                {"lang": "fr", "mpv_id": 7},
            ],
        },
    )
    monkeypatch.setattr(app, "success", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "warn", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "spinner", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "clear_line", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "fetch_subtitle", lambda *_args, **_kwargs: None)

    prefs = {
        "audio_preferences": ["fr", "en", "ja"],
        "subtitle_language": "fr",
        "subtitle_behavior": "when_needed",
    }
    result = app._prepare_playback(
        {"id": 1, "media_type": "movie", "original_language": "ja"},
        "https://example.test/master.m3u8",
        1,
        1,
        prefs,
    )

    assert result["audio_track"] == 2
    assert result["sub_track"] == 7
    assert result["sub_file"] is None


def test_prepare_playback_downloads_external_subtitles_when_needed(monkeypatch):
    monkeypatch.setattr(
        app,
        "detect_tracks",
        lambda _: {
            "audio": [
                {"lang": "ja", "mpv_id": 5},
            ],
            "subs": [],
        },
    )
    monkeypatch.setattr(app, "success", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "warn", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "spinner", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "clear_line", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "get_random_art", lambda: "")
    monkeypatch.setattr(
        app,
        "fetch_subtitle",
        lambda *_args, **_kwargs: "/tmp/subtitle.srt",
    )

    prefs = {
        "audio_preferences": ["fr", "ja", "en"],
        "subtitle_language": "fr",
        "subtitle_behavior": "when_needed",
    }
    result = app._prepare_playback(
        {"id": 2, "media_type": "movie", "original_language": "ja"},
        "https://example.test/master.m3u8",
        1,
        1,
        prefs,
    )

    assert result["audio_track"] == 5
    assert result["sub_track"] is None
    assert result["sub_file"] == "/tmp/subtitle.srt"

