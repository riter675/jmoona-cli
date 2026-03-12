import requests
from .config import TMDB_BASE, TMDB_KEY, TMDB_LANG

class TMDB:
    def __init__(self):
        self.base_url = TMDB_BASE
        self.api_key = TMDB_KEY
        self.lang = TMDB_LANG
        self.session = requests.Session()
        
    def _get(self, endpoint, params=None):
        if params is None:
            params = {}
        params["api_key"] = self.api_key
        params["language"] = self.lang
        try:
            res = self.session.get(f"{self.base_url}{endpoint}", params=params, timeout=10)
            if res.status_code == 200:
                return res.json()
            return {}
        except Exception:
            return {}

    def search(self, query, media_type="multi", year=None):
        params = {"query": query}
        if media_type == "movie":
            endpoint = "/search/movie"
            if year: params["year"] = year
        elif media_type == "tv":
            endpoint = "/search/tv"
            if year: params["first_air_date_year"] = year
        else:
            endpoint = "/search/multi"
            
        data = self._get(endpoint, params=params)
        results = data.get("results", [])
        
        scored_results = []
        for r in results:
            if media_type == "multi" and r.get("media_type") not in ("movie", "tv"):
                continue
            s = self._score(r, query, year)
            scored_results.append((s, r))
            
        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [r for s, r in scored_results]

    def _score(self, result, query, year):
        title = result.get("title") or result.get("name") or ""
        rel = (result.get("release_date") or result.get("first_air_date") or "")[:4]
        votes = result.get("vote_count", 0)
        pop = result.get("popularity", 0)
        
        s = 0
        if title.lower() == query.lower():  s += 10_000_000
        if year and rel == str(year):       s += 5_000_000
        if votes > 20000:                   s += 3_000_000
        elif votes > 10000:                 s += 1_500_000
        elif votes > 5000:                  s += 500_000
        
        s += pop * 10 + votes * 0.1
        return s

    def movie(self, tmdb_id):
        return self._get(f"/movie/{tmdb_id}", {"append_to_response": "credits"})

    def tv(self, tmdb_id):
        return self._get(f"/tv/{tmdb_id}", {"append_to_response": "credits"})

    def season(self, tmdb_id, season_num):
        return self._get(f"/tv/{tmdb_id}/season/{season_num}")

    def episode(self, tmdb_id, season_num, episode_num):
        return self._get(f"/tv/{tmdb_id}/season/{season_num}/episode/{episode_num}")

    def trending(self, media_type="all", window="week"):
        return self._get(f"/trending/{media_type}/{window}").get("results", [])

    def popular(self, media_type="movie"):
        return self._get(f"/{media_type}/popular").get("results", [])

    def top_rated(self, media_type="movie"):
        return self._get(f"/{media_type}/top_rated").get("results", [])

    def discover(self, media_type, genre=None, year=None, lang=None):
        params = {}
        if genre: params["with_genres"] = genre
        if year:
            if media_type == "movie": params["primary_release_year"] = year
            else: params["first_air_date_year"] = year
        if lang: params["with_original_language"] = lang
        
        return self._get(f"/discover/{media_type}", params).get("results", [])

    def translations(self, tmdb_id, media_type):
        data = self._get(f"/{media_type}/{tmdb_id}/translations")
        return [t["iso_639_1"] for t in data.get("translations", [])]

tmdb_client = TMDB()
