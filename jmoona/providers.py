import os
import json
from .config import CONFIG_DIR

# Ordered by reliability.
# Format: (name, movie_url_template, tv_url_template)
# Placeholders: {id}=TMDB ID, {s}=season, {e}=episode, {imdb}=IMDB ID
DEFAULT_PROVIDERS = [
    # ── Tier 1: direct TMDB ID, très fiables ────────────────────────────────
    ("vidsrc.cc",
     "https://vidsrc.cc/v2/embed/movie/{id}",
     "https://vidsrc.cc/v2/embed/tv/{id}/{s}/{e}"),
    ("vidsrc.xyz",
     "https://vidsrc.xyz/embed/movie?tmdb={id}",
     "https://vidsrc.xyz/embed/tv?tmdb={id}&season={s}&episode={e}"),
    ("embed.su",
     "https://embed.su/embed/movie/{id}",
     "https://embed.su/embed/tv/{id}/{s}/{e}"),
    ("vidlink.pro",
     "https://vidlink.pro/movie/{id}",
     "https://vidlink.pro/tv/{id}/{s}/{e}"),
    ("superembed",
     "https://superembed.stream/embed?tmdb_id={id}&type=movie",
     "https://superembed.stream/embed?tmdb_id={id}&type=tv&season={s}&episode={e}"),
    ("videasy",
     "https://player.videasy.net/movie/{id}",
     "https://player.videasy.net/tv/{id}/{s}/{e}"),
    ("vidsrc.in",
     "https://vidsrc.in/embed/movie/{id}",
     "https://vidsrc.in/embed/tv/{id}/{s}/{e}"),
    ("vidsrc.pm",
     "https://vidsrc.pm/embed/movie/{id}",
     "https://vidsrc.pm/embed/tv/{id}/{s}/{e}"),
    ("vidsrc.net",
     "https://vidsrc.net/embed/movie/{id}",
     "https://vidsrc.net/embed/tv/{id}/{s}/{e}"),
    ("vidsrc.nl",
     "https://vidsrc.nl/embed/movie/{id}",
     "https://vidsrc.nl/embed/tv/{id}/{s}/{e}"),
    ("vidbinge",
     "https://vidbinge.com/embed/movie/{id}",
     "https://vidbinge.com/embed/tv/{id}/{s}/{e}"),
    ("rgshows",
     "https://rgshows.com/movie/{id}",
     "https://rgshows.com/tv/{id}/{s}/{e}"),
    # ── Tier 2: fiables mais parfois lents ──────────────────────────────────
    ("vidsrc.to",
     "https://vidsrc.to/embed/movie/{id}",
     "https://vidsrc.to/embed/tv/{id}/{s}/{e}"),
    ("vidsrc.me",
     "https://vidsrc.me/embed/movie?tmdb={id}",
     "https://vidsrc.me/embed/tv?tmdb={id}&season={s}&episode={e}"),
    ("autoembed",
     "https://autoembed.co/movie/tmdb/{id}",
     "https://autoembed.co/tv/tmdb/{id}-{s}-{e}"),
    ("2embed",
     "https://www.2embed.cc/embed/{id}",
     "https://www.2embed.cc/embedtv/{id}&s={s}&e={e}"),
    ("2embed.skin",
     "https://www.2embed.skin/embed/{id}",
     "https://www.2embed.skin/embedtv/{id}&s={s}&e={e}"),
    ("moviesapi",
     "https://moviesapi.club/movie/{id}",
     "https://moviesapi.club/tv/{id}-{s}-{e}"),
    ("multiembed",
     "https://multiembed.mov/?video_id={id}&tmdb=1",
     "https://multiembed.mov/?video_id={id}&tmdb=1&s={s}&e={e}"),
    ("smashystream",
     "https://player.smashy.stream/movie/{id}",
     "https://player.smashy.stream/tv/{id}?s={s}&e={e}"),
    # ── Tier 3: spéciaux / sources rares ────────────────────────────────────
    ("frembed",
     "https://frembed.pro/api/film.php?id={id}",
     "https://frembed.pro/api/serie.php?id={id}&sa={s}&epi={e}"),
    ("frembed.lol",
     "https://frembed.lol/api/film.php?id={id}",
     "https://frembed.lol/api/serie.php?id={id}&sa={s}&epi={e}"),
    ("embedc.in",
     "https://embedc.in/embed/movie/{id}?autostart=0",
     "https://embedc.in/embed/tv/{id}/{s}/{e}?autostart=0"),
    ("watcha.pro",
     "https://watcha.pro/en/movie/{id}",
     "https://watcha.pro/en/tv/{id}"),
]

# Providers that accept IMDB ID instead of TMDB ID (used as fallback for rare content)
IMDB_PROVIDERS = [
    ("vidsrc.me-imdb",
     "https://vidsrc.me/embed/movie?imdb={imdb}",
     "https://vidsrc.me/embed/tv?imdb={imdb}&season={s}&episode={e}"),
    ("2embed-imdb",
     "https://www.2embed.cc/embed/{imdb}",
     "https://www.2embed.cc/embedtv/{imdb}&s={s}&e={e}"),
    ("vidsrc.to-imdb",
     "https://vidsrc.to/embed/movie/{imdb}",
     "https://vidsrc.to/embed/tv/{imdb}/{s}/{e}"),
    ("vidsrc.in-imdb",
     "https://vidsrc.in/embed/movie/{imdb}",
     "https://vidsrc.in/embed/tv/{imdb}/{s}/{e}"),
    ("vidsrc.pm-imdb",
     "https://vidsrc.pm/embed/movie/{imdb}",
     "https://vidsrc.pm/embed/tv/{imdb}/{s}/{e}"),
    ("vidsrc.net-imdb",
     "https://vidsrc.net/embed/movie/{imdb}",
     "https://vidsrc.net/embed/tv/{imdb}/{s}/{e}"),
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
