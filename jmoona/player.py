"""
player.py — Launch the media player with proper flags.
Supports: mpv (primary), vlc (fallback), and any custom player.
"""
import os
import shutil
import subprocess
import urllib.parse
import json
from .config import UA
from .ui import warn, success


def _parse_headers_from_url(stream_url):
    """Extract Referer / Origin embedded in proxy-style URLs."""
    referer = "https://cloudnestra.com/"
    origin  = "https://cloudnestra.com"
    try:
        parsed = urllib.parse.urlparse(stream_url)
        if "headers=" in stream_url:
            qs = urllib.parse.parse_qs(parsed.query)
            if "headers" in qs:
                hdict = json.loads(qs["headers"][0])
                referer = hdict.get("referer", referer)
                origin  = hdict.get("origin",  origin)
    except Exception:
        pass
    return referer, origin


def _detect_player():
    """Auto-detect the best available player."""
    for p in ["mpv", "vlc", "celluloid", "mplayer"]:
        if shutil.which(p):
            return p
    return None


def play(stream_url, title="", sub_path=None, player="mpv",
         player_args="--fs", audio_lang=None, sub_lang=None,
         audio_track=None, sub_track=None, resume_pos=None):

    # Auto-detect player if requested
    if not player or player == "auto":
        player = _detect_player() or "mpv"

    if not shutil.which(player):
        warn(f"Le lecteur '{player}' est introuvable. Installation requise.")
        fallback = _detect_player()
        if fallback:
            warn(f"Utilisation de '{fallback}' à la place.")
            player = fallback
        else:
            warn("Aucun lecteur vidéo trouvé. Installez mpv ou vlc.")
            return

    referer, origin = _parse_headers_from_url(stream_url)
    is_vidlink = "vodvidl" in stream_url or "storm.vodvidl" in stream_url

    # ── mpv ──────────────────────────────────────────────────────────────────
    if player == "mpv":
        cmd = ["mpv"]
        if title:
            cmd += [f"--title={title}"]
        if resume_pos:
            cmd += [f"--start={int(resume_pos)}"]

        cmd += [
            "--save-position-on-quit",
            f"--user-agent={UA}",
            "--force-seekable=yes",
        ]

        if is_vidlink:
            cmd += [
                "--no-ytdl",
                f"--referrer={referer}",
                f"--http-header-fields=Origin: {origin}",
            ]
        else:
            cmd += [
                "--referrer=https://cloudnestra.com/",
                "--http-header-fields=Origin: https://cloudnestra.com",
            ]

        # HLS reliability: buffering + reconnect
        cmd += [
            "--cache=yes",
            "--demuxer-max-bytes=64M",
            "--demuxer-max-back-bytes=20M",
            "--stream-lavf-o=reconnect_on_http_error=4xx,5xx,reconnect_delay_max=5",
            "--demuxer-lavf-o=http_persistent=0",
            "--network-timeout=30",
        ]

        # Audio / subtitles
        if audio_track is not None:
            cmd += [f"--aid={audio_track}"]
        elif audio_lang:
            cmd += [f"--alang={audio_lang}"]

        if sub_path and (sub_path.startswith("http") or os.path.exists(sub_path)):
            cmd += [f"--sub-file={sub_path}"]
            if sub_track is None:
                cmd += ["--sid=1"]
            else:
                cmd += [f"--sid={sub_track}"]
        elif sub_track is not None:
            cmd += [f"--sid={sub_track}"]
        elif sub_lang == "off":
            cmd += ["--no-sub"]
        elif sub_lang:
            cmd += [f"--slang={sub_lang}"]

        if player_args:
            cmd += player_args.split()

        cmd.append(stream_url)

    # ── VLC ───────────────────────────────────────────────────────────────────
    elif player == "vlc":
        cmd = ["vlc", "--play-and-exit"]
        if title:
            cmd += [f"--meta-title={title}"]
        # HTTP headers
        cmd += [
            f"--http-referrer={referer}",
            "--http-reconnect",
        ]
        if resume_pos:
            cmd += [f"--start-time={int(resume_pos)}"]
        if audio_lang:
            cmd += [f"--preferred-language={audio_lang}"]
        if sub_path and (sub_path.startswith("http") or os.path.exists(sub_path)):
            cmd += [f"--sub-file={sub_path}"]
        if player_args:
            cmd += player_args.split()
        cmd.append(stream_url)

    # ── Generic ───────────────────────────────────────────────────────────────
    else:
        warn(f"Lecteur personnalisé : {player} (support limité)")
        cmd = [player]
        if player_args:
            cmd += player_args.split()
        cmd.append(stream_url)

    try:
        subprocess.run(cmd)
    except FileNotFoundError:
        warn(f"Le lecteur '{player}' n'est pas installé ou introuvable.")
    except Exception as e:
        warn(f"Erreur lors de la lecture: {e}")
