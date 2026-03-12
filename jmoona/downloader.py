import os
import re
import subprocess
from .config import UA

def sanitize(filename):
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def download(stream_url, title, out_dir, quality="best",
             audio_lang=None, sub_path=None, proxy=None):

    qmap = {
        "best":  "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "4k":    "bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/best",
        "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best",
        "720p":  "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best",
        "480p":  "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best",
    }

    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"{sanitize(title)}.%(ext)s")

    cmd = [
        "yt-dlp",
        "-f", qmap.get(quality, qmap["best"]),
        "-o", out_file,
        "--add-header", f"User-Agent:{UA}",
        "--add-header", "Referer:https://cloudnestra.com/",
        "--add-header", "Origin:https://cloudnestra.com",
        "--hls-use-mpegts",
        "--no-playlist",
        "--progress",
        "--merge-output-format", "mp4",
        "--embed-thumbnail",
        "--add-metadata",
        "--limit-rate", "3M",                 # Prevent 429 Too Many Requests
        "--fragment-retries", "infinite",
    ]
    if audio_lang: cmd += ["--audio-language", audio_lang]
    if sub_path:   cmd += ["--embed-subs", "--sub-lang", sub_path]
    if proxy:      cmd += ["--proxy", proxy]
    
    if "vidlink.pro" in stream_url or "vodvidl" in stream_url:
        cmd += ["--extractor-args", "generic:impersonate"]

    cmd.append(stream_url)

    try:
        subprocess.run(cmd)
    except FileNotFoundError:
        print("yt-dlp n'est pas installé. Lancez : sudo apt install yt-dlp")

def download_season(tmdb_id, season_num, out_dir, quality="best", lang="fr"):
    from .tmdb import tmdb_client
    from .extractor import extract
    
    season_data = tmdb_client.season(tmdb_id, season_num)
    for ep in season_data.get("episodes", []):
        ep_num = ep["episode_number"]
        print(f"\nExtraction S{season_num:02d}E{ep_num:02d}...")
        stream_url = extract(tmdb_id, "tv", season_num, ep_num, quality=quality, lang=lang)
        if stream_url:
            title = f"S{season_num:02d}E{ep_num:02d} - {ep.get('name', '')}"
            download(stream_url, title, out_dir, quality=quality, audio_lang=lang)
