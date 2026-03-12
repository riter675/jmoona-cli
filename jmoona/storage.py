import os
import json
from .config import CONFIG_DIR, DEFAULT_CONFIG

CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
HISTORY_PATH = os.path.join(CONFIG_DIR, "history.json")
RESUME_PATH = os.path.join(CONFIG_DIR, "resume.json")
BOOKMARKS_PATH = os.path.join(CONFIG_DIR, "bookmarks.json")


def _entry_tmdb_id(entry):
    return entry.get("tmdb_id", entry.get("id"))


def _normalize_entry(entry):
    normalized = dict(entry)
    tmdb_id = _entry_tmdb_id(normalized)
    if tmdb_id is not None:
        normalized["tmdb_id"] = tmdb_id
    return normalized

def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def load_config():
    config = DEFAULT_CONFIG.copy()
    user_config = load_json(CONFIG_PATH, {})
    config.update(user_config)
    save_config(config)
    return config

def save_config(config):
    save_json(CONFIG_PATH, config)

def add_history(entry):
    config = load_config()
    history = load_json(HISTORY_PATH, [])
    entry = _normalize_entry(entry)
    entry_tmdb_id = _entry_tmdb_id(entry)
    # Remove existing entry with same identifier if present
    history = [
        h for h in history
        if not (
            _entry_tmdb_id(h) == entry_tmdb_id
            and h.get("media_type") == entry.get("media_type")
            and h.get("season") == entry.get("season")
            and h.get("episode") == entry.get("episode")
        )
    ]
    history.insert(0, entry)
    if len(history) > config.get("history_limit", 1000):
        history = history[:config.get("history_limit", 1000)]
    save_json(HISTORY_PATH, history)

def get_history():
    return load_json(HISTORY_PATH, [])

def clear_history():
    save_json(HISTORY_PATH, [])

def save_resume(key, position, timestamp):
    resume = load_json(RESUME_PATH, {})
    resume[key] = {"position": position, "ts": timestamp}
    save_json(RESUME_PATH, resume)

def get_resume(key):
    resume = load_json(RESUME_PATH, {})
    return resume.get(key, {}).get("position")

def get_bookmarks():
    return load_json(BOOKMARKS_PATH, [])

def save_bookmarks(bookmarks):
    save_json(BOOKMARKS_PATH, bookmarks)

def add_bookmark(entry):
    bookmarks = get_bookmarks()
    entry = _normalize_entry(entry)
    entry_tmdb_id = _entry_tmdb_id(entry)
    bookmarks = [
        b for b in bookmarks
        if not (
            _entry_tmdb_id(b) == entry_tmdb_id
            and b.get("media_type") == entry.get("media_type")
        )
    ]
    bookmarks.insert(0, entry)
    save_bookmarks(bookmarks)

def remove_bookmark(tmdb_id, media_type):
    bookmarks = get_bookmarks()
    bookmarks = [
        b for b in bookmarks
        if not (_entry_tmdb_id(b) == tmdb_id and b.get("media_type") == media_type)
    ]
    save_bookmarks(bookmarks)
