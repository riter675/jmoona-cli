"""
app.py — Main application logic for jmoona-cli v1.0.4
New features:
  • Episode browser showing total episodes per season
  • Auto-next episode mode (if config auto_next=True)
  • Retry menu when extraction fails
  • Discover by genre and by original language
  • Richer details panel (genres, runtime, country)
"""
import sys
import os
from . import __version__
from .ui import C, fzf_or_numbered, _strip_ansi, success, warn, error, clear_line, spinner
from .tmdb import tmdb_client
from .storage import load_config, add_history, get_history, get_bookmarks, add_bookmark, get_resume
from .extractor import extract
from .player import play
from .language import detect_tracks, get_lang_label, normalize_lang
from .downloader import download
from .art import get_random_art
from .subtitles import fetch_subtitle


def format_item(item):
    title   = item.get("title") or item.get("name") or "Inconnu"
    date    = (item.get("release_date") or item.get("first_air_date") or "")[:4]
    date_str = f"({date})" if date else ""
    vt = item.get("vote_count", 0)
    vt_str = f"{vt/1000:.1f}k" if vt > 1000 else str(vt)
    icon = "🎬" if item.get("media_type", "movie") == "movie" else "📺"
    orig_lang = item.get("original_language", "")
    lang_flag = f"  {C.GRAY}[{orig_lang.upper()}]{C.RESET}" if orig_lang and orig_lang != "fr" else ""
    return (f"{icon} {C.BOLD}{title}{C.RESET}  {C.DIM}{date_str}{C.RESET}"
            f"  {C.YELLOW}★{item.get('vote_average', 0):.1f}{C.RESET}"
            f"  {C.DIM}{vt_str} votes{C.RESET}{lang_flag}")


def print_details(item):
    title    = item.get("title") or item.get("name") or "Inconnu"
    date     = (item.get("release_date") or item.get("first_air_date") or "")[:4]
    mtype    = "🎬 Film" if item.get("media_type", "movie") == "movie" else "📺 Série"
    overview = item.get("overview", "Aucune description.")
    if len(overview) > 180:
        overview = overview[:177] + "..."

    # Genres
    genres = item.get("genres", [])
    if not genres:
        # Try from list format (search results have genre_ids not genres)
        genre_ids = item.get("genre_ids", [])
        if genre_ids:
            genres = [{"name": str(g)} for g in genre_ids[:3]]
    genre_str = " · ".join(g["name"] for g in genres[:4]) if genres else ""

    # Runtime / episodes
    runtime = item.get("runtime") or item.get("episode_run_time", [None])[0] if isinstance(item.get("episode_run_time"), list) else item.get("runtime")
    runtime_str = f"  |  {runtime} min" if runtime else ""

    # Country
    countries = item.get("production_countries", []) or item.get("origin_country", [])
    if isinstance(countries, list) and countries:
        if isinstance(countries[0], dict):
            country_str = f"  |  {countries[0].get('iso_3166_1', '')}"
        else:
            country_str = f"  |  {countries[0]}"
    else:
        country_str = ""

    # Credits
    crew_str = ""
    cast_str = ""
    if "credits" in item:
        director = [c["name"] for c in item["credits"].get("crew", []) if c.get("job") == "Director"]
        if director:
            crew_str = f"🎥 De {', '.join(director[:2])}"
        cast = [c["name"] for c in item["credits"].get("cast", [])]
        if cast:
            cast_str = f"🎭 {', '.join(cast[:3])}"

    print(f"\n{C.CYAN}════════════════════════════════════════════════════════════{C.RESET}")
    print(f"  {C.BOLD}{title}{C.RESET}  ({date})  {mtype}{runtime_str}{country_str}")
    print(f"  {C.YELLOW}★{item.get('vote_average', 0):.1f}/10{C.RESET}  |  {item.get('vote_count', 0)} votes", end="")
    if "original_language" in item:
        print(f"  |  VO: {get_lang_label(item['original_language'])}", end="")
    print()
    if genre_str:
        print(f"  {C.DIM}{genre_str}{C.RESET}")
    if crew_str or cast_str:
        sep = "  |  " if crew_str and cast_str else ""
        print(f"  {C.GREEN}{crew_str}{sep}{cast_str}{C.RESET}")
    print(f"\n  {C.DIM}{overview}{C.RESET}")
    print(f"{C.CYAN}════════════════════════════════════════════════════════════{C.RESET}")


def select_media(results, config, prompt="Résultats"):
    if not results:
        warn("Aucun résultat.")
        return None
    return fzf_or_numbered(results, prompt, format_item, use_fzf=config.get("use_fzf", True))


def _unique_langs(values):
    seen = set()
    ordered = []
    for value in values:
        if not value:
            continue
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _configured_audio_langs(config):
    raw = config.get("lang", ["fr", "en"])
    if isinstance(raw, str):
        raw = [part.strip() for part in raw.split(",")]
    return _unique_langs(normalize_lang(lang) for lang in raw if lang)


def _resolve_playback_preferences(item, args, config):
    original_lang = normalize_lang(item.get("original_language") or "en")
    default_sub = normalize_lang(config.get("sub_lang", "fr"))
    requested_audio = (getattr(args, "lang", None) or "").strip().lower() if args else ""
    requested_sub = (getattr(args, "sub", None) or "").strip().lower() if args else ""
    configured_audio = _configured_audio_langs(config) or ["fr", "en"]
    subtitles_disabled = requested_sub == "off"

    if subtitles_disabled:
        requested_sub = ""
    subtitle_language = None if subtitles_disabled else (
        normalize_lang(requested_sub) if requested_sub else default_sub
    )

    if requested_audio:
        if requested_audio in ("vostfr", "vosfr"):
            return {
                "lang_mode": "vostfr",
                "audio_preferences": _unique_langs([original_lang, "en"]),
                "subtitle_language": subtitle_language,
                "subtitle_behavior": "always",
            }
        if requested_audio in ("va", "vo", "original", "orig"):
            return {
                "lang_mode": "va",
                "audio_preferences": _unique_langs([original_lang, "en"]),
                "subtitle_language": normalize_lang(requested_sub) if requested_sub else None,
                "subtitle_behavior": "always" if requested_sub else "never",
            }

        requested = normalize_lang(requested_audio)
        subtitle_lang = normalize_lang(requested_sub) if requested_sub else None
        return {
            "lang_mode": "custom",
            "audio_preferences": _unique_langs([requested, original_lang, "en", "fr"]),
            "subtitle_language": subtitle_lang,
            "subtitle_behavior": "always" if subtitle_lang else "never",
        }

    is_anime = item.get("original_language") in ("ja", "ko", "zh")
    lang_menu = [
        ("🎵  Auto  — VF si disponible, sinon VOSTFR", "auto"),
        ("🔤  VOSTFR  — VO + sous-titres français", "vostfr"),
        ("🇬🇧  VA  — Version originale uniquement", "va"),
    ]
    lang_choice = fzf_or_numbered(
        lang_menu,
        "Mode de lecture",
        lambda x: x[0],
        use_fzf=config.get("use_fzf", True),
    )
    lang_mode = lang_choice[1] if lang_choice else ("vostfr" if is_anime else "auto")

    if lang_mode == "vostfr":
        return {
            "lang_mode": lang_mode,
            "audio_preferences": _unique_langs([original_lang, "en"]),
            "subtitle_language": default_sub,
            "subtitle_behavior": "always",
        }
    if lang_mode == "va":
        return {
            "lang_mode": lang_mode,
            "audio_preferences": _unique_langs([original_lang, "en"]),
            "subtitle_language": None,
            "subtitle_behavior": "never",
        }
    return {
        "lang_mode": "auto",
        "audio_preferences": _unique_langs(configured_audio + [original_lang, "en"]),
        "subtitle_language": default_sub,
        "subtitle_behavior": "when_needed",
    }


def _pick_track_by_language(tracks, preferred_languages):
    for preferred in preferred_languages:
        for track in tracks:
            if normalize_lang(track.get("lang", "")) == preferred:
                return track
    return tracks[0] if tracks else None


def _prepare_playback(item, stream_url, season, episode, prefs):
    audio_preferences = prefs["audio_preferences"]
    subtitle_language = prefs["subtitle_language"]
    subtitle_behavior = prefs["subtitle_behavior"]
    audio_lang_mpv = ",".join(audio_preferences) if audio_preferences else "en"
    audio_track = None
    sub_track = None
    sub_file = None
    selected_audio_lang = None

    track_info = detect_tracks(stream_url)
    if track_info.get("audio"):
        audio_track = _pick_track_by_language(track_info["audio"], audio_preferences)
        selected_audio_lang = normalize_lang(audio_track.get("lang", "")) if audio_track else None

    wants_subtitles = bool(subtitle_language) and subtitle_behavior == "always"
    if (
        subtitle_behavior == "when_needed"
        and subtitle_language
        and selected_audio_lang
        and selected_audio_lang != "fr"
    ):
        wants_subtitles = True

    if wants_subtitles and track_info.get("subs"):
        preferred_sub = _pick_track_by_language(track_info["subs"], [subtitle_language])
        if preferred_sub:
            sub_track = preferred_sub.get("mpv_id")
            success(f"Sous-titres intégrés: {get_lang_label(preferred_sub['lang'])}")

    if wants_subtitles and sub_track is None:
        spinner("Recherche de sous-titres ...", art=get_random_art())
        sub_file = fetch_subtitle(
            item["id"],
            item["media_type"],
            lang=subtitle_language,
            season=season,
            episode=episode,
        )
        clear_line()
        if sub_file:
            success(f"Sous-titres chargés: {os.path.basename(sub_file)}")
        else:
            warn("Aucun sous-titre correspondant trouvé.")

    return {
        "audio_lang_mpv": audio_lang_mpv,
        "audio_track": audio_track.get("mpv_id") if audio_track else None,
        "sub_track": sub_track,
        "sub_file": sub_file,
        "selected_audio_lang": selected_audio_lang,
    }


def main_flow(query=None, args=None):
    config = load_config()
    if args and getattr(args, 'no_fzf', False):
        config["use_fzf"] = False

    if query:
        spinner(f"Recherche de '{query}'...", art=get_random_art())
        results = tmdb_client.search(query, media_type=getattr(args, 'type', 'multi') or 'multi')
        clear_line()
        item = select_media(results, config, "Choisir un titre")
        if item:
            handle_item(item, args, config)
        return

    menu = [
        ("🎬  Chercher un film",    lambda: handle_search("movie", args, config)),
        ("📺  Chercher une série",  lambda: handle_search("tv",    args, config)),
        ("🔥  Tendances",           lambda: handle_list(tmdb_client.trending(), "Tendances", args, config)),
        ("⭐  Films populaires",    lambda: handle_list(tmdb_client.popular("movie"), "Films Populaires", args, config)),
        ("📡  Séries populaires",   lambda: handle_list(tmdb_client.popular("tv"), "Séries Populaires", args, config)),
        ("🏆  Mieux notés",         lambda: handle_list(tmdb_client.top_rated("movie"), "Mieux Notés", args, config)),
        ("🎭  Par genre",           lambda: handle_by_genre(args, config)),
        ("🌐  Par langue originale",lambda: handle_by_language(args, config)),
        ("👤  Par acteur/réalisateur", lambda: handle_by_person(args, config)),
        ("🎲  Surprenez-moi !",     lambda: handle_random(args, config)),
        ("🕒  Historique",          lambda: handle_history(args, config)),
        ("🔖  Favoris",             lambda: handle_bookmarks(args, config)),
        ("👋  Quitter",             lambda: sys.exit(0)),
    ]

    ASCII_LOGO = rf"""{C.MAGENTA}
      _                                        _ _ 
     (_)                                      | (_)
      _ _ __ ___   ___   ___  _ __   __ _  ___| | |
     | | '_ ` _ \ / _ \ / _ \| '_ \ / _` |/ __| | |
     | | | | | | | (_) | (_) | | | | (_| | (__| | |
     | |_| |_| |_|\___/ \___/|_| |_|\__,_|\___|_|_|
    _/ |                                           
   |__/  {C.RESET}{C.DIM}v{__version__} — Films & séries du monde{C.RESET}
    """
    if not query:
        print("\033c", end="")
        print(ASCII_LOGO)
        print(f"  {C.BOLD}{C.CYAN}Bienvenue sur jmoona — le meilleur streamer CLI.{C.RESET}\n")
        print(get_random_art())
        try:
            input(f"\n  {C.DIM}Appuyez sur Entrée pour continuer...{C.RESET}")
        except (KeyboardInterrupt, EOFError):
            sys.exit(0)
        print("\033c", end="")
        print(ASCII_LOGO)
        print(f"  {C.BOLD}{C.CYAN}Menu Principal{C.RESET}\n")

    choice = fzf_or_numbered(menu, "Menu principal", lambda x: x[0], use_fzf=config.get("use_fzf", True))
    if choice:
        choice[1]()


def handle_search(mtype, args, config):
    q = input(f"\nRecherche ({'Film' if mtype == 'movie' else 'Série'}) : ").strip()
    if q:
        spinner("Recherche...", art=get_random_art())
        results = tmdb_client.search(q, media_type=mtype)
        clear_line()
        item = select_media(results, config, "Résultats")
        if item:
            item["media_type"] = mtype
            handle_item(item, args, config)


def handle_by_person(args, config):
    q = input(f"\nRecherche d'une personne (Acteur/Réalisateur) : ").strip()
    if not q:
        return
    spinner("Recherche...", art=get_random_art())
    persons = tmdb_client.search_person(q)
    clear_line()
    if not persons:
        warn("Aucune personne trouvée.")
        return
        
    def fmt_person(p):
        dep = p.get("known_for_department", "Inconnu")
        return f"👤 {C.BOLD}{p['name']}{C.RESET}  {C.DIM}({dep}){C.RESET}"
        
    person = fzf_or_numbered(persons, "Choisir une personne", fmt_person, use_fzf=config.get("use_fzf", True))
    if not person:
        return
        
    spinner(f"Chargement de la filmographie de {person['name']}...", art=get_random_art())
    credits = tmdb_client.person_credits(person["id"])
    clear_line()
    
    # Merge cast and crew, sort by popularity
    works = credits.get("cast", []) + [w for w in credits.get("crew", []) if w.get("job") == "Director"]
    # deduplicate by id
    seen = set()
    unique_works = []
    for w in works:
        if w["id"] not in seen and w.get("media_type") in ("movie", "tv"):
            seen.add(w["id"])
            unique_works.append(w)
            
    unique_works.sort(key=lambda x: x.get("popularity", 0), reverse=True)
    if not unique_works:
        warn("Aucune oeuvre trouvée pour cette personne.")
        return
    
    handle_list(unique_works, f"Filmographie — {person['name']}", args, config)


def handle_random(args, config):
    mtype_choices = [("🎬 Film aléatoire", "movie"), ("📺 Série aléatoire", "tv")]
    mtype_choice  = fzf_or_numbered(mtype_choices, "Type", lambda x: x[0],
                                    use_fzf=config.get("use_fzf", True))
    if not mtype_choice:
        return
    mtype = mtype_choice[1]
    
    spinner("Génération magique d'un titre...", art=get_random_art())
    item = tmdb_client.random_title(media_type=mtype)
    clear_line()
    if item:
        item["media_type"] = mtype
        handle_item(item, args, config)
    else:
        warn("Erreur lors de la génération aléatoire.")


def handle_list(items, title, args, config):
    item = select_media(items, config, title)
    if item:
        if "media_type" not in item:
            item["media_type"] = "tv" if "first_air_date" in item else "movie"
        handle_item(item, args, config)


def handle_history(args, config):
    history = get_history()
    if not history:
        warn("Historique vide.")
        return
    item = select_media(history, config, "Historique")
    if item:
        handle_item(item, args, config)


def handle_bookmarks(args, config):
    bookmarks = get_bookmarks()
    if not bookmarks:
        warn("Favoris vides.")
        return
    item = select_media(bookmarks, config, "Favoris")
    if item:
        handle_item(item, args, config)


def handle_by_genre(args, config):
    """Browse by genre → discover titles."""
    mtype_choices = [("🎬 Films", "movie"), ("📺 Séries", "tv")]
    mtype_choice  = fzf_or_numbered(mtype_choices, "Type", lambda x: x[0],
                                    use_fzf=config.get("use_fzf", True))
    if not mtype_choice:
        return
    mtype = mtype_choice[1]

    spinner("Chargement des genres...", art=get_random_art())
    genres = tmdb_client.genres(mtype)
    clear_line()
    if not genres:
        warn("Impossible de charger les genres.")
        return

    genre = fzf_or_numbered(genres, "Genre", lambda g: g["name"],
                            use_fzf=config.get("use_fzf", True))
    if not genre:
        return

    spinner(f"Chargement des {mtype}s — {genre['name']}...", art=get_random_art())
    results = tmdb_client.discover(mtype, genre=genre["id"])
    for r in results:
        r["media_type"] = mtype
    clear_line()
    handle_list(results, genre["name"], args, config)


def handle_by_language(args, config):
    """Browse by original language."""
    LANGUAGES = [
        ("🇫🇷 Français",   "fr"), ("🇬🇧 Anglais",  "en"), ("🇯🇵 Japonais", "ja"),
        ("🇰🇷 Coréen",     "ko"), ("🇪🇸 Espagnol", "es"), ("🇩🇪 Allemand", "de"),
        ("🇮🇹 Italien",    "it"), ("🇵🇹 Portugais","pt"), ("🇷🇺 Russe",    "ru"),
        ("🇨🇳 Chinois",    "zh"), ("🇮🇳 Hindi",    "hi"), ("🇸🇦 Arabe",    "ar"),
        ("🇹🇷 Turc",       "tr"), ("🇳🇱 Néerlandais","nl"),("🇵🇱 Polonais","pl"),
        ("🇸🇪 Suédois",    "sv"), ("🇩🇰 Danois",   "da"), ("🇫🇮 Finnois",  "fi"),
        ("🇬🇷 Grec",       "el"), ("🇮🇱 Hébreu",   "he"), ("🇹🇭 Thaï",    "th"),
    ]
    lang = fzf_or_numbered(LANGUAGES, "Langue originale", lambda x: x[0],
                           use_fzf=config.get("use_fzf", True))
    if not lang:
        return

    mtype_choices = [("🎬 Films", "movie"), ("📺 Séries", "tv")]
    mtype_choice  = fzf_or_numbered(mtype_choices, "Type", lambda x: x[0],
                                    use_fzf=config.get("use_fzf", True))
    if not mtype_choice:
        return
    mtype = mtype_choice[1]

    spinner(f"Chargement {lang[0]}...", art=get_random_art())
    results = tmdb_client.discover(mtype, lang=lang[1])
    for r in results:
        r["media_type"] = mtype
    clear_line()
    handle_list(results, f"{lang[0]}", args, config)


def _pick_episode(item, args, config):
    """Pick season + episode with info on total counts."""
    tmdb_id = item["id"]

    # Get season list
    spinner("Chargement des saisons...", art=get_random_art())
    tv_detail = tmdb_client.tv(tmdb_id)
    clear_line()

    seasons_raw = tv_detail.get("seasons", [])
    # Filter real seasons (not specials if season 0)
    seasons = [s for s in seasons_raw if s.get("season_number", 0) > 0]
    if not seasons:
        seasons = [{"season_number": 1, "episode_count": 1}]

    season_labels = [
        f"Saison {s['season_number']}  ({s.get('episode_count', '?')} épisodes)"
        for s in seasons
    ]
    season_items = list(zip(season_labels, seasons))
    season_choice = fzf_or_numbered(
        season_items, "Saison", lambda x: x[0],
        use_fzf=config.get("use_fzf", True)
    )
    if not season_choice:
        return None, None
    chosen_season = season_choice[1]
    season_num = chosen_season["season_number"]
    ep_count   = chosen_season.get("episode_count", 1)

    # Episode picker with numbers
    ep_items   = [f"Épisode {e}" for e in range(1, ep_count + 1)]
    ep_choice  = fzf_or_numbered(
        list(enumerate(ep_items, 1)), "Épisode", lambda x: x[1],
        use_fzf=config.get("use_fzf", True)
    )
    if not ep_choice:
        return season_num, 1
    return season_num, ep_choice[0]


def handle_item(item, args, config):
    if "media_type" not in item:
        item["media_type"] = "tv" if "first_air_date" in item else "movie"

    # Enrich with extra details from TMDB if needed
    if "genres" not in item and item.get("id"):
        try:
            if item["media_type"] == "movie":
                detail = tmdb_client.movie(item["id"])
            else:
                detail = tmdb_client.tv(item["id"])
            item.update({k: v for k, v in detail.items() if k not in item})
        except Exception:
            pass

    print_details(item)

    if args and getattr(args, "download", False):
        choice = "⬇ Télécharger"
    else:
        opts = ["▶ Regarder", "⬇ Télécharger", "🔖 Ajouter aux favoris", "🔙 Retour"]
        choice = fzf_or_numbered(
            opts,
            "Action",
            lambda x: x,
            use_fzf=config.get("use_fzf", True),
        )

    if not choice or "Retour" in choice:
        return

    if "Favoris" in choice:
        add_bookmark(item)
        success("Ajouté aux favoris.")
        return

    # Season / episode selection
    season, episode = 1, 1
    if item["media_type"] == "tv":
        if args and getattr(args, 'season', None) and getattr(args, 'episode', None):
            season, episode = args.season, args.episode
        else:
            s, e = _pick_episode(item, args, config)
            if s is None:
                return
            season, episode = s, e

    provider = (args.provider if args and getattr(args, 'provider', None)
                else config.get("provider", "auto"))
    quality  = (args.quality if args and getattr(args, 'quality', None)
                else config.get("quality", "best"))
    proxy = (args.proxy if args and getattr(args, "proxy", None)
             else config.get("proxy"))
    prefs = _resolve_playback_preferences(item, args, config)

    # --- Extraction loop with retry ---
    stream_url = None
    vtt_url    = None
    while stream_url is None:
        stream_url, vtt_url = extract(
            item["id"], item["media_type"], season, episode,
            quality=quality,
            lang=prefs["audio_preferences"][0],
            proxy=proxy,
            provider=provider,
        )

        if not stream_url:
            error("Impossible de trouver un flux vidéo.")
            retry_opts = [
                ("🔄 Réessayer avec tous les providers", "retry_all"),
                ("🔌 Changer de provider",               "change_provider"),
                ("🔙 Retour au menu",                    "back"),
            ]
            retry = fzf_or_numbered(retry_opts, "Que faire ?", lambda x: x[0],
                                    use_fzf=config.get("use_fzf", True))
            if not retry or retry[1] == "back":
                return
            elif retry[1] == "change_provider":
                from .providers import PROVIDERS
                prov_names = [p[0] for p in PROVIDERS] + ["auto"]
                prov_choice = fzf_or_numbered(prov_names, "Choisir un provider",
                                              lambda x: x,
                                              use_fzf=config.get("use_fzf", True))
                if prov_choice:
                    provider = prov_choice
            # else retry_all: just loop again

    playback = _prepare_playback(item, stream_url, season, episode, prefs)

    history_entry = dict(item)
    if item["media_type"] == "tv":
        history_entry["season"] = season
        history_entry["episode"] = episode
    add_history(history_entry)

    if "Télécharger" in choice:
        out_dir = os.path.expanduser(
            args.download_dir if args and getattr(args, "download_dir", None)
            else config.get("download_dir", "~/Downloads/jmoona")
        )
        title_str = item.get("title") or item.get("name")
        if item["media_type"] == "tv":
            title_str += f" S{season:02d}E{episode:02d}"
        download(
            stream_url,
            title_str,
            out_dir,
            quality=quality,
            audio_lang=playback["audio_lang_mpv"] or "en",
            sub_path=playback["sub_file"],
            proxy=proxy,
        )
        return

    # Play
    rkey = f"{item['media_type']}_{item['id']}"
    if item["media_type"] == "tv":
        rkey += f"_s{season}e{episode}"
    resume_pos = get_resume(rkey)
    player_name = (args.player if args and getattr(args, "player", None)
                   else config.get("player", "mpv"))

    play(
        stream_url,
        title=(item.get("title") or item.get("name")),
        player=player_name,
        player_args=config.get("player_args", "--fs"),
        audio_lang=playback["audio_lang_mpv"],
        sub_path=playback["sub_file"],
        audio_track=playback["audio_track"],
        sub_track=playback["sub_track"],
        resume_pos=resume_pos,
    )

    # Auto-next episode
    if (config.get("auto_next", False) and item["media_type"] == "tv"):
        _attempt_next_episode(item, season, episode, args, config,
                              prefs, provider, quality, proxy)


def _attempt_next_episode(item, season, episode, args, config,
                           prefs, provider, quality, proxy):
    """Auto-play the next episode if available."""
    try:
        season_info = tmdb_client.season(item["id"], season)
        ep_count    = len(season_info.get("episodes", []))
    except Exception:
        return

    next_ep  = episode + 1
    next_s   = season
    if next_ep > ep_count:
        # Try next season
        next_ep = 1
        next_s  = season + 1

    print(f"\n  {C.DIM}Épisode suivant : S{next_s:02d}E{next_ep:02d}{C.RESET}")
    try:
        ans = input(f"  {C.BOLD}▶ Lancer S{next_s:02d}E{next_ep:02d} ? [O/n]{C.RESET} ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        return
    if ans in ("", "o", "y", "oui", "yes"):
        item_next = dict(item)
        handle_item_direct(item_next, next_s, next_ep, args, config,
                           prefs, provider, quality, proxy)


def handle_item_direct(item, season, episode, args, config,
                        prefs, provider, quality, proxy):
    """Play a specific season/episode directly (used by auto-next)."""
    stream_url, _ = extract(
        item["id"], item["media_type"], season, episode,
        quality=quality,
        lang=prefs["audio_preferences"][0],
        proxy=proxy,
        provider=provider,
    )
    if not stream_url:
        error(f"Flux introuvable pour S{season:02d}E{episode:02d}.")
        return

    playback = _prepare_playback(item, stream_url, season, episode, prefs)

    history_entry = dict(item, season=season, episode=episode)
    add_history(history_entry)

    rkey = f"{item['media_type']}_{item['id']}_s{season}e{episode}"
    resume_pos = get_resume(rkey)
    player_name = (args.player if args and getattr(args, "player", None)
                   else config.get("player", "mpv"))

    play(
        stream_url,
        title=f"{item.get('title') or item.get('name')} S{season:02d}E{episode:02d}",
        player=player_name,
        player_args=config.get("player_args", "--fs"),
        audio_lang=playback["audio_lang_mpv"],
        sub_path=playback["sub_file"],
        audio_track=playback["audio_track"],
        sub_track=playback["sub_track"],
        resume_pos=resume_pos,
    )

    if config.get("auto_next", False):
        _attempt_next_episode(item, season, episode, args, config,
                              prefs, provider, quality, proxy)
