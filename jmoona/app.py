import sys
import os
from .ui import C, fzf_or_numbered, _strip_ansi, success, warn, error, clear_line, spinner
from .tmdb import tmdb_client
from .storage import load_config, add_history, get_history, get_bookmarks, add_bookmark, get_resume
from .extractor import extract
from .player import play
from .language import detect_tracks, get_lang_label
from .downloader import download
from .art import get_random_art
from .subtitles import fetch_subtitle

def format_item(item):
    title = item.get("title") or item.get("name") or "Inconnu"
    date = (item.get("release_date") or item.get("first_air_date") or "")[:4]
    date_str = f"({date})" if date else ""
    vt = item.get("vote_count", 0)
    if vt > 1000: vt_str = f"{vt/1000:.1f}k"
    else: vt_str = str(vt)
    icon = "🎬" if item.get("media_type", "movie") == "movie" else "📺"
    return f"{icon} {C.BOLD}{title}{C.RESET}  {C.DIM}{date_str}{C.RESET}  {C.YELLOW}★{item.get('vote_average', 0):.1f}{C.RESET}  {C.DIM}{vt_str} votes{C.RESET}"

def print_details(item):
    title = item.get("title") or item.get("name") or "Inconnu"
    date = (item.get("release_date") or item.get("first_air_date") or "")[:4]
    mtype = "🎬 Film" if item.get("media_type", "movie") == "movie" else "📺 Série"
    overview = item.get("overview", "Aucune description.")
    if len(overview) > 150:
        overview = overview[:147] + "..."
    
    print(f"\n{C.CYAN}════════════════════════════════════════════════════════════{C.RESET}")
    print(f"  {C.BOLD}{title}{C.RESET}  ({date})  {mtype}")
    print(f"  {C.YELLOW}★{item.get('vote_average', 0):.1f}/10{C.RESET}  |  {item.get('vote_count', 0)} votes")
    if "original_language" in item:
        print(f"  Langue originale: {get_lang_label(item['original_language'])}")
    print(f"\n  {C.DIM}{overview}{C.RESET}")
    print(f"{C.CYAN}════════════════════════════════════════════════════════════{C.RESET}")

def select_media(results, config, prompt="Résultats"):
    if not results:
        warn("Aucun résultat.")
        return None
    return fzf_or_numbered(results, prompt, format_item, use_fzf=config.get("use_fzf", True))

def main_flow(query=None, args=None):
    config = load_config()
    if args and getattr(args, 'no_fzf', False):
        config["use_fzf"] = False
    
    if query:
        spinner(f"Recherche de '{query}'...", art=get_random_art())
        results = tmdb_client.search(query, media_type=getattr(args, 'type', 'multi') or 'multi')
        clear_line()
        item = select_media(results, config, "Choisir un titre")
        if item: handle_item(item, args, config)
        return

    menu = [
        ("🎬  Chercher un film", lambda: handle_search("movie", args, config)),
        ("📺  Chercher une série", lambda: handle_search("tv", args, config)),
        ("🔥  Tendances", lambda: handle_list(tmdb_client.trending(), "Tendances", args, config)),
        ("⭐  Films populaires", lambda: handle_list(tmdb_client.popular("movie"), "Films Populaires", args, config)),
        ("📡  Séries populaires", lambda: handle_list(tmdb_client.popular("tv"), "Séries Populaires", args, config)),
        ("🏆  Mieux notés", lambda: handle_list(tmdb_client.top_rated("movie"), "Mieux Notés", args, config)),
        ("🕒  Historique", lambda: handle_history(args, config)),
        ("🔖  Favoris", lambda: handle_bookmarks(args, config)),
        ("👋  Quitter", lambda: sys.exit(0))
    ]
    
    ASCII_LOGO = rf"""{C.MAGENTA}
      _                                        _ _ 
     (_)                                      | (_)
      _ _ __ ___   ___   ___  _ __   __ _  ___| |_ 
     | | '_ ` _ \ / _ \ / _ \| '_ \ / _` |/ __| | |
     | | | | | | | (_) | (_) | | | | (_| | (__| | |
     | |_| |_| |_|\___/ \___/|_| |_|\__,_|\___|_|_|
    _/ |                                           
   |__/  {C.RESET}{C.DIM}v1.0.0 - L'émulateur ultime de films et séries{C.RESET}
    """
    if not query:
        print("\033c", end="")  # Clear screen
        print(ASCII_LOGO)
        print(f"  {C.BOLD}{C.CYAN}Bienvenue sur votre émulateur de films et séries by jmoona.{C.RESET}\n")
        print(get_random_art())
        try:
            input(f"\n  {C.DIM}Appuyez sur Entrée pour continuer...{C.RESET}")
        except (KeyboardInterrupt, EOFError):
            sys.exit(0)
        print("\033c", end="")  # Clear screen again before menu
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
    if item: handle_item(item, args, config)

def handle_bookmarks(args, config):
    bookmarks = get_bookmarks()
    if not bookmarks:
        warn("Favoris vides.")
        return
    item = select_media(bookmarks, config, "Favoris")
    if item: handle_item(item, args, config)

def handle_item(item, args, config):
    if "media_type" not in item:
        item["media_type"] = "tv" if "first_air_date" in item else "movie"
        
    print_details(item)
    opts = ["▶ Regarder", "⬇ Télécharger", "🔖 Ajouter aux favoris", "🔙 Retour"]
    choice = fzf_or_numbered(opts, "Action", lambda x: x, use_fzf=config.get("use_fzf", True))
    
    if not choice or "Retour" in choice:
        return
        
    if "Favoris" in choice:
        add_bookmark(item)
        success("Ajouté aux favoris.")
        return

    season, episode = 1, 1
    if item["media_type"] == "tv":
        if args and getattr(args, 'season', None) and getattr(args, 'episode', None):
            season, episode = args.season, args.episode
        else:
            try:
                s_str = input("Saison (défaut=1) : ").strip()
                if s_str: season = int(s_str)
                e_str = input("Épisode (défaut=1) : ").strip()
                if e_str: episode = int(e_str)
            except ValueError:
                pass
                
    provider = args.provider if args and getattr(args, 'provider', None) else config.get("provider", "auto")
    quality = args.quality if args and getattr(args, 'quality', None) else config.get("quality", "best")
    
    # Mode de lecture (simple)
    is_anime = item.get("original_language") in ("ja", "ko", "zh")
    lang_menu = [
        ("🎵  Auto  — FR si disponible, sinon VO (recommandé)", "auto"),
        ("🔤  VOSTFR  — VO + sous-titres français", "vostfr"),
        ("🇬🇧  VA  — Version originale uniquement", "va"),
    ]
    lang_choice = fzf_or_numbered(lang_menu, "Mode de lecture", lambda x: x[0], use_fzf=config.get("use_fzf", True))
    lang_mode = lang_choice[1] if lang_choice else ("vostfr" if is_anime else "auto")

    stream_url, _ = extract(item["id"], item["media_type"], season, episode, quality=quality, lang="en", provider=provider)

    if not stream_url:
        error("Impossible de trouver un flux vidéo.")
        return

    # Audio language preference for mpv (no slow track scan needed)
    audio_lang_mpv = {
        "auto":   "fr,en",   # mpv picks FR if available, falls back to EN
        "va":     "en",
        "vostfr": "en",      # keep original audio, subs handle French
    }.get(lang_mode, "en")

    # Subtitles — VOSTFR only
    sub_file = None
    if lang_mode == "vostfr":
        spinner("Recherche de sous-titres français ...", art=get_random_art())
        sub_file = fetch_subtitle(item["id"], item["media_type"], lang="fr", season=season, episode=episode)
        clear_line()
        if sub_file:
            success(f"✓ VOSTFR — {os.path.basename(sub_file)}")
        else:
            warn("Aucun sous-titre FR disponible sur OpenSubtitles — lecture en VO.")


    item["episode"] = episode
    add_history(item)

    if "Télécharger" in choice:
        out_dir = os.path.expanduser(config.get("download_dir", "~/Downloads/jmoona"))
        title = item.get("title") or item.get("name")
        if item["media_type"] == "tv":
            title += f" S{season:02d}E{episode:02d}"
        
        download(stream_url, title, out_dir, quality=quality,
                 audio_lang=audio_lang_mpv or "en",
                 sub_path=sub_file)
    else:
        rkey = f"{item['media_type']}_{item['id']}"
        if item["media_type"] == "tv":
            rkey += f"_s{season}e{episode}"
            
        resume_pos = get_resume(rkey)
        
        play(
            stream_url,
            title=(item.get("title") or item.get("name")),
            player=config.get("player", "mpv"),
            player_args=config.get("player_args", "--fs"),
            audio_lang=audio_lang_mpv,
            sub_path=sub_file,
            resume_pos=resume_pos
        )
