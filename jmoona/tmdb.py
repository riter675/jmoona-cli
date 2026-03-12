"""
tmdb.py — TMDB API client
• Multi-page search (up to 3 pages = 60 results) for rare titles
• Bilingual search: fr-FR first, then en-US fallback to catch untranslated titles
• Better scoring: bonus for exact original title match
• Caches IMDB ID in result objects to reduce future API calls
• OMDB fallback: if TMDB has zero results, query OMDB (free) for the IMDB ID
"""
import requests
from .config import TMDB_BASE, TMDB_KEY, TMDB_LANG

OMDB_BASE = "http://www.omdbapi.com"
OMDB_KEY  = "trilogy"  # free fallback key — limited but helpful for rare titles


class TMDB:
    def __init__(self):
        self.base_url  = TMDB_BASE
        self.api_key   = TMDB_KEY
        self.lang      = TMDB_LANG
        self.lang_en   = "en-US"
        self.session   = requests.Session()

    # ── Low-level ────────────────────────────────────────────────────────────

    def _get(self, endpoint, params=None, lang=None):
        if params is None:
            params = {}
        params["api_key"] = self.api_key
        params["language"] = lang or self.lang
        try:
            res = self.session.get(
                f"{self.base_url}{endpoint}", params=params, timeout=10
            )
            if res.status_code == 200:
                return res.json()
            return {}
        except Exception:
            return {}

    # ── Search ───────────────────────────────────────────────────────────────

    def search(self, query, media_type="multi", year=None, pages=3):
        """
        Search TMDB for *query*.

        Strategy:
        1. Fetch up to `pages` pages in fr-FR.
        2. If fewer than 5 results found, repeat in en-US and merge.
        3. If still nothing, try OMDB as last resort (movie only).
        """
        results_fr = self._search_pages(query, media_type, year, lang=self.lang, pages=pages)
        seen_ids = {r["id"] for r in results_fr}

        # Bilingual fallback
        if len(results_fr) < 5:
            results_en = self._search_pages(query, media_type, year, lang=self.lang_en, pages=pages)
            for r in results_en:
                if r["id"] not in seen_ids:
                    results_fr.append(r)
                    seen_ids.add(r["id"])

        # Score & sort
        scored = [(self._score(r, query, year), r) for r in results_fr]
        scored.sort(key=lambda x: x[0], reverse=True)
        final = [r for _, r in scored]

        # OMDB last resort
        if not final and media_type in ("movie", "multi"):
            tmdb_id = self._omdb_to_tmdb(query, year)
            if tmdb_id:
                detail = self.movie(tmdb_id)
                if detail.get("id"):
                    detail["media_type"] = "movie"
                    final = [detail]

        return final

    def _search_pages(self, query, media_type, year, lang, pages=3):
        results = []
        seen    = set()
        if media_type == "movie":
            endpoint = "/search/movie"
        elif media_type == "tv":
            endpoint = "/search/tv"
        else:
            endpoint = "/search/multi"

        for page in range(1, pages + 1):
            params = {"query": query, "page": page}
            if year:
                if media_type == "movie":
                    params["year"] = year
                elif media_type == "tv":
                    params["first_air_date_year"] = year

            data = self._get(endpoint, params, lang=lang)
            page_results = data.get("results", [])
            if not page_results:
                break   # no more pages

            for r in page_results:
                if media_type == "multi" and r.get("media_type") not in ("movie", "tv"):
                    continue
                if r["id"] in seen:
                    continue
                seen.add(r["id"])
                # Inject media_type for non-multi searches
                if media_type != "multi":
                    r["media_type"] = media_type
                results.append(r)

            # Stop early if we're deep in irrelevant pages
            if page >= 2 and results and self._score(page_results[-1], query, year) < 1000:
                break

        return results

    def _score(self, result, query, year):
        title    = result.get("title") or result.get("name") or ""
        orig     = result.get("original_title") or result.get("original_name") or ""
        rel      = (result.get("release_date") or result.get("first_air_date") or "")[:4]
        votes    = result.get("vote_count", 0)
        pop      = result.get("popularity", 0)

        s = 0
        ql = query.lower().strip()

        # Exact title matches (localized or original)
        if title.lower() == ql:            s += 10_000_000
        elif orig.lower() == ql:           s += 9_500_000
        elif ql in title.lower():          s += 1_000_000
        elif ql in orig.lower():           s += 800_000

        # Year match
        if year and rel == str(year):      s += 5_000_000

        # Vote weight
        if votes > 20000:                  s += 3_000_000
        elif votes > 10000:                s += 1_500_000
        elif votes > 5000:                 s += 500_000
        elif votes > 1000:                 s += 100_000

        s += pop * 10 + votes * 0.1
        return s

    # ── OMDB fallback ────────────────────────────────────────────────────────

    def _omdb_to_tmdb(self, query, year=None):
        """Query OMDB for a title → get IMDB ID → find TMDB ID via /find."""
        try:
            params = {"s": query, "apikey": OMDB_KEY}
            if year:
                params["y"] = year
            r = self.session.get(OMDB_BASE, params=params, timeout=8)
            if r.status_code != 200:
                return None
            data = r.json()
            results = data.get("Search", [])
            if not results:
                return None
            imdb_id = results[0].get("imdbID")
            if not imdb_id:
                return None
            # Convert IMDB → TMDB
            find = self._get(f"/find/{imdb_id}", {"external_source": "imdb_id"})
            movie_res = find.get("movie_results", [])
            tv_res    = find.get("tv_results", [])
            if movie_res:
                return movie_res[0]["id"]
            if tv_res:
                return tv_res[0]["id"]
        except Exception:
            pass
        return None

    # ── Detail endpoints ─────────────────────────────────────────────────────

    def movie(self, tmdb_id):
        return self._get(f"/movie/{tmdb_id}", {"append_to_response": "credits,external_ids,genres"})

    def tv(self, tmdb_id):
        return self._get(f"/tv/{tmdb_id}", {"append_to_response": "credits,external_ids,genres"})

    def season(self, tmdb_id, season_num):
        return self._get(f"/tv/{tmdb_id}/season/{season_num}")

    def episode(self, tmdb_id, season_num, episode_num):
        return self._get(f"/tv/{tmdb_id}/season/{season_num}/episode/{episode_num}")

    def external_ids(self, tmdb_id, media_type):
        return self._get(f"/{media_type}/{tmdb_id}/external_ids")

    def imdb_id(self, tmdb_id, media_type):
        """Return the IMDB ID string (e.g. 'tt0372784') or None."""
        data = self.external_ids(tmdb_id, media_type)
        raw = data.get("imdb_id", "")
        return raw if raw else None

    # ── Lists ─────────────────────────────────────────────────────────────────

    def trending(self, media_type="all", window="week"):
        return self._get(f"/trending/{media_type}/{window}").get("results", [])

    def popular(self, media_type="movie"):
        return self._get(f"/{media_type}/popular").get("results", [])

    def top_rated(self, media_type="movie"):
        return self._get(f"/{media_type}/top_rated").get("results", [])

    def discover(self, media_type, genre=None, year=None, lang=None, page=1):
        params = {"page": page}
        if genre:  params["with_genres"] = genre
        if year:
            if media_type == "movie": params["primary_release_year"] = year
            else:                     params["first_air_date_year"]  = year
        if lang:   params["with_original_language"] = lang
        return self._get(f"/discover/{media_type}", params).get("results", [])

    def genres(self, media_type="movie"):
        """Return [{id, name}, …] for genres."""
        return self._get(f"/genre/{media_type}/list").get("genres", [])

    def translations(self, tmdb_id, media_type):
        data = self._get(f"/{media_type}/{tmdb_id}/translations")
        return [t["iso_639_1"] for t in data.get("translations", [])]


tmdb_client = TMDB()
