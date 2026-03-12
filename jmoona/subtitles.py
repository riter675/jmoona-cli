"""
subtitles.py — Fetch subtitles from multiple sources
Priority:
  1. OpenSubtitles XML-RPC (legacy but widely supported)
  2. OpenSubtitles REST API v1 (opensubtitles.com)
  3. subdl.com (free, no key needed)
"""
import os
import gzip
import tempfile
import json
import xmlrpc.client
import urllib.request
import urllib.parse

from . import __version__

OPENSUBTITLES_UA  = f"jmoona-cli v{__version__}"
OPENSUBTITLES_API = "https://api.opensubtitles.org/xml-rpc"
OPENSUBTITLES_REST= "https://api.opensubtitles.com/api/v1"
SUBDL_API         = "https://api.subdl.com/api/v1/subtitles"

# ISO 639-1 → ISO 639-2/B (OpenSubtitles XML-RPC)
LANG_MAP_XMLRPC = {
    "fr": "fre", "en": "eng", "es": "spa", "de": "ger",
    "it": "ita", "pt": "por", "ar": "ara", "ru": "rus",
    "ja": "jpn", "ko": "kor", "zh": "chi", "nl": "dut",
    "pl": "pol", "tr": "tur", "sv": "swe", "da": "dan",
    "fi": "fin", "no": "nor", "cs": "cze", "ro": "rum",
    "hu": "hun", "he": "heb", "el": "ell", "th": "tha",
    "vi": "vie", "id": "ind", "ms": "may",
}

# ISO 639-1 → subdl.com language codes
LANG_MAP_SUBDL = {
    "fr": "FR", "en": "EN", "es": "ES", "de": "DE",
    "it": "IT", "pt": "PT", "ar": "AR", "ru": "RU",
    "ja": "JA", "ko": "KO", "zh": "ZH", "nl": "NL",
    "pl": "PL", "tr": "TR", "sv": "SV",
}


def _imdb_id_from_tmdb(tmdb_id: int, media_type: str) -> str | None:
    try:
        from .tmdb import tmdb_client
        return tmdb_client.imdb_id(tmdb_id, media_type)
    except Exception:
        return None


def _download_sub(url, out_path, ua=None):
    """Download a URL to out_path. Handles gzip. Returns True on success."""
    try:
        headers = {"User-Agent": ua or OPENSUBTITLES_UA}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read()
        try:
            data = gzip.decompress(raw)
        except Exception:
            data = raw
        with open(out_path, "wb") as f:
            f.write(data)
        return True
    except Exception:
        return False


def _fetch_xmlrpc(imdb_id, lang, media_type, season, episode, out_dir):
    """OpenSubtitles XML-RPC (legacy)."""
    os3_lang = LANG_MAP_XMLRPC.get(lang, lang)
    clean_imdb = imdb_id.lstrip("t") if imdb_id else None
    if not clean_imdb:
        return None
    try:
        server = xmlrpc.client.ServerProxy(OPENSUBTITLES_API)
        login = server.LogIn("", "", "en", OPENSUBTITLES_UA)
        token = login.get("token", "")
        if not token:
            return None

        query = {"sublanguageid": os3_lang, "imdbid": clean_imdb}
        if media_type == "tv":
            query["season"]  = str(season)
            query["episode"] = str(episode)

        result = server.SearchSubtitles(token, [query])
        subs   = result.get("data", [])
        server.LogOut(token)

        if not subs:
            return None

        subs.sort(key=lambda x: int(x.get("SubDownloadsCnt", 0)), reverse=True)
        best = subs[0]
        dl_url = best.get("SubDownloadLink", "")
        fmt    = best.get("SubFormat", "srt")
        if not dl_url:
            return None

        out_path = os.path.join(
            out_dir, f"jmoona_sub_{clean_imdb}_s{season}e{episode}_{lang}.{fmt}"
        )
        if _download_sub(dl_url, out_path):
            return out_path
    except Exception:
        pass
    return None


def _fetch_rest(tmdb_id, lang, media_type, season, episode, out_dir):
    """OpenSubtitles REST API v1 (no key needed for public search)."""
    try:
        params = {
            "tmdb_id": tmdb_id,
            "languages": lang,
            "type": "movie" if media_type == "movie" else "episode",
        }
        if media_type == "tv":
            params["season_number"]  = season
            params["episode_number"] = episode

        query_string = urllib.parse.urlencode(params)
        url = f"{OPENSUBTITLES_REST}/subtitles?{query_string}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent":  OPENSUBTITLES_UA,
                "Content-Type": "application/json",
                "Api-Key": "srtLpHqjQEAK3O5o49HMJJ7E3Jq3Xv5N",  # public free key
            }
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())

        subs = data.get("data", [])
        if not subs:
            return None

        # Sort by download count
        subs.sort(
            key=lambda x: x.get("attributes", {}).get("download_count", 0),
            reverse=True
        )
        best_attrs = subs[0].get("attributes", {})
        files = best_attrs.get("files", [])
        if not files:
            return None

        file_id = files[0].get("file_id")
        if not file_id:
            return None

        # Request download link
        dl_req = urllib.request.Request(
            f"{OPENSUBTITLES_REST}/download",
            data=json.dumps({"file_id": file_id}).encode(),
            headers={
                "User-Agent":   OPENSUBTITLES_UA,
                "Content-Type": "application/json",
                "Api-Key": "srtLpHqjQEAK3O5o49HMJJ7E3Jq3Xv5N",
            },
            method="POST"
        )
        with urllib.request.urlopen(dl_req, timeout=10) as r:
            dl_data = json.loads(r.read().decode())

        dl_url = dl_data.get("link")
        if not dl_url:
            return None

        out_path = os.path.join(
            out_dir, f"jmoona_sub_{tmdb_id}_s{season}e{episode}_{lang}.srt"
        )
        if _download_sub(dl_url, out_path):
            return out_path
    except Exception:
        pass
    return None


def _fetch_subdl(imdb_id, lang, media_type, season, episode, out_dir):
    """subdl.com — free API, no key required."""
    if not imdb_id:
        return None
    sl = LANG_MAP_SUBDL.get(lang, lang.upper())
    try:
        params = {
            "imdb_id": imdb_id.lstrip("t"),
            "languages": sl,
            "subs_per_page": 5,
        }
        if media_type == "tv":
            params["season"]  = season
            params["episode"] = episode

        query_string = urllib.parse.urlencode(params)
        url = f"{SUBDL_API}?{query_string}"
        req = urllib.request.Request(
            url, headers={"User-Agent": OPENSUBTITLES_UA}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())

        subs = data.get("subtitles", [])
        if not subs:
            return None

        best = subs[0]
        dl_url = best.get("url")
        if not dl_url:
            return None
        if not dl_url.startswith("http"):
            dl_url = "https://dl.subdl.com" + dl_url

        out_path = os.path.join(
            out_dir, f"jmoona_subdl_{imdb_id}_s{season}e{episode}_{lang}.srt"
        )
        if _download_sub(dl_url, out_path, ua=OPENSUBTITLES_UA):
            return out_path
    except Exception:
        pass
    return None


def fetch_subtitle(
    tmdb_id: int,
    media_type: str,
    lang: str = "fr",
    season: int = 1,
    episode: int = 1,
    out_dir: str | None = None,
) -> str | None:
    """
    Download the best matching subtitle and return its local path.
    Tries: XML-RPC → REST API → subdl.com
    Returns None if nothing found.
    """
    if out_dir is None:
        out_dir = tempfile.gettempdir()

    imdb_id = _imdb_id_from_tmdb(tmdb_id, media_type)

    # 1. OpenSubtitles XML-RPC
    path = _fetch_xmlrpc(imdb_id, lang, media_type, season, episode, out_dir)
    if path:
        return path

    # 2. OpenSubtitles REST API v1
    path = _fetch_rest(tmdb_id, lang, media_type, season, episode, out_dir)
    if path:
        return path

    # 3. subdl.com
    path = _fetch_subdl(imdb_id, lang, media_type, season, episode, out_dir)
    return path
