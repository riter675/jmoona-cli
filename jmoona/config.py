import os
import sys

__version__ = "1.0.6"

# --- Cross-platform config directory ---
def _default_config_dir() -> str:
    """Return the appropriate config dir for the current OS."""
    if sys.platform == "win32":
        # Windows: %APPDATA%\jmoona (e.g. C:\Users\User\AppData\Roaming\jmoona)
        return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "jmoona")
    elif sys.platform == "darwin":
        # macOS: ~/Library/Application Support/jmoona
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "jmoona")
    else:
        # Linux/BSD: $XDG_CONFIG_HOME/jmoona or ~/.config/jmoona
        xdg = os.environ.get("XDG_CONFIG_HOME", "")
        base = xdg if xdg else os.path.join(os.path.expanduser("~"), ".config")
        return os.path.join(base, "jmoona")

def _default_download_dir() -> str:
    """Return the OS Downloads folder."""
    if sys.platform == "win32":
        # Windows: ~/Downloads/jmoona
        return os.path.join(os.path.expanduser("~"), "Downloads", "jmoona")
    else:
        return os.path.join(os.path.expanduser("~"), "Downloads", "jmoona")

CONFIG_DIR = _default_config_dir()
os.makedirs(CONFIG_DIR, exist_ok=True)

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_KEY  = "8265bd1679663a7ea12ac168da84d2e8"
TMDB_LANG = "fr-FR"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

DEFAULT_CONFIG = {
  "player": "mpv",
  "player_args": "--fs",
  "download_dir": _default_download_dir(),
  "quality": "best",
  "provider": "auto",
  "lang": ["fr", "en"],
  "sub_lang": "fr",
  "sub_auto": True,
  "history_limit": 1000,
  "results_limit": 60,
  "use_fzf": True,
  "auto_next": False,
  "resume": True,
  "proxy": None,
  "concurrent_search": True,
  "tmdb_key": TMDB_KEY,
  "opensubtitles_key": ""
}
