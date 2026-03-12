from jmoona import storage


def _set_storage_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(storage, "HISTORY_PATH", str(tmp_path / "history.json"))
    monkeypatch.setattr(storage, "RESUME_PATH", str(tmp_path / "resume.json"))
    monkeypatch.setattr(storage, "BOOKMARKS_PATH", str(tmp_path / "bookmarks.json"))
    storage.save_json(storage.CONFIG_PATH, {"history_limit": 10})


def test_add_history_deduplicates_entries_with_plain_id(monkeypatch, tmp_path):
    _set_storage_paths(monkeypatch, tmp_path)

    entry = {"id": 42, "media_type": "movie", "title": "Example"}
    storage.add_history(entry)
    storage.add_history(dict(entry))

    history = storage.get_history()
    assert len(history) == 1
    assert history[0]["tmdb_id"] == 42
    assert history[0]["id"] == 42


def test_add_bookmark_deduplicates_entries_with_plain_id(monkeypatch, tmp_path):
    _set_storage_paths(monkeypatch, tmp_path)

    entry = {"id": 7, "media_type": "tv", "name": "Series"}
    storage.add_bookmark(entry)
    storage.add_bookmark(dict(entry))

    bookmarks = storage.get_bookmarks()
    assert len(bookmarks) == 1
    assert bookmarks[0]["tmdb_id"] == 7

