import os
import json
from .config import CONFIG_DIR

DEFAULT_PROVIDERS = [
    ("vidsrc.xyz",
     "https://vidsrc.xyz/embed/movie?tmdb={id}",
     "https://vidsrc.xyz/embed/tv?tmdb={id}&season={s}&episode={e}"),
    ("vidsrc.me",
     "https://vidsrc.me/embed/movie?tmdb={id}",
     "https://vidsrc.me/embed/tv?tmdb={id}&season={s}&episode={e}"),
    ("vidsrc.to",
     "https://vidsrc.to/embed/movie/{id}",
     "https://vidsrc.to/embed/tv/{id}/{s}/{e}"),
    ("embed.su",
     "https://embed.su/embed/movie/{id}",
     "https://embed.su/embed/tv/{id}/{s}/{e}"),
    ("autoembed",
     "https://autoembed.co/movie/tmdb/{id}",
     "https://autoembed.co/tv/tmdb/{id}-{s}-{e}"),
    ("2embed",
     "https://www.2embed.cc/embed/{id}",
     "https://www.2embed.cc/embedtv/{id}&s={s}&e={e}"),
    ("moviesapi",
     "https://moviesapi.club/movie/{id}",
     "https://moviesapi.club/tv/{id}-{s}-{e}"),
    ("nontonfilm",
     "https://nontonfilm.fun/api/movie/{id}",
     "https://nontonfilm.fun/api/tv/{id}/{s}/{e}"),
    ("multiembed",
     "https://multiembed.mov/?video_id={id}&tmdb=1",
     "https://multiembed.mov/?video_id={id}&tmdb=1&s={s}&e={e}"),
    ("smashystream",
     "https://player.smashy.stream/movie/{id}",
     "https://player.smashy.stream/tv/{id}?s={s}&e={e}"),
]

def load_providers():
    providers_path = os.path.join(CONFIG_DIR, "providers.json")
    if os.path.exists(providers_path):
        try:
            with open(providers_path, "r", encoding="utf-8") as f:
                custom = json.load(f)
                if isinstance(custom, list) and len(custom) > 0:
                    return [tuple(p) for p in custom if len(p) == 3]
        except Exception:
            pass
    return DEFAULT_PROVIDERS

PROVIDERS = load_providers()
