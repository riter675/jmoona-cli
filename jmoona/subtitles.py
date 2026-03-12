"""
subtitles.py — Fetch subtitles from OpenSubtitles (XML-RPC, no key needed)
Uses the TMDB → IMDB ID mapping we already have, downloads .srt to /tmp.
"""
import os
import gzip
import tempfile
import xmlrpc.client
import urllib.request

OPENSUBTITLES_UA = "jmoona-cli v1.0.0"
OPENSUBTITLES_API = "https://api.opensubtitles.org/xml-rpc"

LANG_MAP = {
    "fr": "fre",
    "en": "eng",
    "es": "spa",
    "de": "ger",
    "it": "ita",
    "pt": "por",
}


def _imdb_id_from_tmdb(tmdb_id: int, media_type: str):
    """Use TMDB API to get the IMDB ID."""
    try:
        from .tmdb import tmdb_client
        if media_type == "movie":
            data = tmdb_client._get(f"/movie/{tmdb_id}/external_ids")
        else:
            data = tmdb_client._get(f"/tv/{tmdb_id}/external_ids")
        imdb = data.get("imdb_id", "")
        return imdb.lstrip("t") if imdb else None
    except Exception:
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
    Returns None if nothing found.
    """
    os3_lang = LANG_MAP.get(lang, lang)
    imdb_id = _imdb_id_from_tmdb(tmdb_id, media_type)
    if not imdb_id:
        return None

    try:
        server = xmlrpc.client.ServerProxy(OPENSUBTITLES_API)
        login = server.LogIn("", "", "en", OPENSUBTITLES_UA)
        token = login.get("token", "")
        if not token:
            return None

        query = {"sublanguageid": os3_lang, "imdbid": imdb_id}
        if media_type == "tv":
            query["season"] = str(season)
            query["episode"] = str(episode)

        result = server.SearchSubtitles(token, [query])
        subs = result.get("data", [])
        server.LogOut(token)

        if not subs:
            return None

        # Pick the best subtitle (most downloads first)
        subs.sort(key=lambda x: int(x.get("SubDownloadsCnt", 0)), reverse=True)
        best = subs[0]
        download_url = best.get("SubDownloadLink", "")
        sub_format = best.get("SubFormat", "srt")

        if not download_url:
            return None

        if out_dir is None:
            out_dir = tempfile.gettempdir()
        out_path = os.path.join(out_dir, f"jmoona_sub_{tmdb_id}_s{season}e{episode}_{lang}.{sub_format}")

        req = urllib.request.Request(download_url, headers={"User-Agent": OPENSUBTITLES_UA})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()

        # OpenSubtitles returns gzipped content
        try:
            data = gzip.decompress(raw)
        except Exception:
            data = raw

        with open(out_path, "wb") as f:
            f.write(data)

        return out_path

    except Exception:
        return None
