import argparse
import json
import sys
from .app import main_flow
from .__init__ import __version__


def main():
    parser = argparse.ArgumentParser(description="Films et séries du monde en streaming.")
    parser.add_argument("query", nargs="?", help='Titre à rechercher (ex: "Parasite 2019")')
    parser.add_argument("-t", "--type", choices=["movie", "tv", "multi"], default=None, help="Type de contenu")
    parser.add_argument("-s", "--season", type=int, help="Numéro de saison")
    parser.add_argument("-e", "--episode", type=int, help="Numéro d'épisode")
    parser.add_argument("-q", "--quality", choices=["best", "1080p", "720p", "480p", "4k"], default=None, help="Qualité vidéo")
    parser.add_argument("-l", "--lang", help="Langue audio souhaitée")
    parser.add_argument("--sub", help="Langue sous-titres")
    parser.add_argument("-p", "--player", default=None, help="Lecteur vidéo")
    parser.add_argument("--provider", help="Forcer un provider spécifique")
    parser.add_argument("--proxy", help="Proxy HTTP/SOCKS5")
    parser.add_argument("--download", action="store_true", help="Télécharger au lieu de streamer")
    parser.add_argument("--download-dir", help="Dossier de téléchargement")
    parser.add_argument("--trending", action="store_true", help="Afficher les tendances")
    parser.add_argument("--popular", action="store_true", help="Films/Séries populaires")
    parser.add_argument("--top-rated", action="store_true", help="Mieux notés")
    parser.add_argument("--history", action="store_true", help="Afficher l'historique")
    parser.add_argument("--bookmarks", action="store_true", help="Afficher les favoris")
    parser.add_argument("--config", action="store_true", help="Ouvrir les paramètres")
    parser.add_argument("--clear-history", action="store_true", help="Effacer l'historique")
    parser.add_argument("--no-fzf", action="store_true", help="Désactiver fzf")
    parser.add_argument("--debug", action="store_true", help="Mode debug")
    parser.add_argument("-V", "--version", action="version", version=f"jmoona-cli {__version__}")

    args = parser.parse_args()

    try:
        if args.trending:
            from .app import handle_list
            from .tmdb import tmdb_client
            from .storage import load_config
            handle_list(tmdb_client.trending(), "Tendances", args, load_config())
        elif args.popular:
            from .app import handle_list
            from .tmdb import tmdb_client
            from .storage import load_config
            handle_list(tmdb_client.popular(), "Populaire", args, load_config())
        elif args.top_rated:
            from .app import handle_list
            from .tmdb import tmdb_client
            from .storage import load_config
            handle_list(tmdb_client.top_rated(), "Mieux notés", args, load_config())
        elif args.history:
            from .app import handle_history
            from .storage import load_config
            handle_history(args, load_config())
        elif args.bookmarks:
            from .app import handle_bookmarks
            from .storage import load_config
            handle_bookmarks(args, load_config())
        elif args.config:
            from .storage import load_config, CONFIG_PATH
            print(CONFIG_PATH)
            print(json.dumps(load_config(), indent=2, ensure_ascii=False))
        elif args.clear_history:
            from .storage import clear_history
            clear_history()
            print("\033[92m✓\033[0m Historique effacé.")
        else:
            main_flow(args.query, args)
    except KeyboardInterrupt:
        print("\n\033[90mInterrompu.\033[0m")
        sys.exit(1)

if __name__ == "__main__":
    main()
