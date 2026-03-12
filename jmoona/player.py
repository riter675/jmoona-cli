import os
import subprocess
from .config import UA
from .ui import warn

def play(stream_url, title="", sub_path=None, player="mpv",
         player_args="--fs", audio_lang=None, sub_lang=None,
         audio_track=None, sub_track=None, resume_pos=None):

    if player == "mpv":
        cmd = ["mpv"]
        if title:      
            cmd += [f"--title={title}"]
        if resume_pos: 
            cmd += [f"--start={int(resume_pos)}"]
            
        cmd += ["--save-position-on-quit"]
        cmd += [f"--user-agent={UA}"]
        
        # Parse headers if embedded in the stream_url (like Vidlink)
        import urllib.parse
        parsed = urllib.parse.urlparse(stream_url)
        referer = "https://cloudnestra.com/"
        origin = "https://cloudnestra.com"
        
        if "headers=" in stream_url:
            import json as _json
            try:
                qs = urllib.parse.parse_qs(parsed.query)
                if "headers" in qs:
                    hdict = _json.loads(qs["headers"][0])
                    referer = hdict.get("referer", referer)
                    origin = hdict.get("origin", origin)
            except: pass

        is_vidlink = "vodvidl" in stream_url or "storm.vodvidl" in stream_url

        if is_vidlink:
            # VidLink proxy: bypass yt-dlp, stream HLS directly via ffmpeg
            # This avoids Cloudflare triggering again through yt-dlp
            cmd += ["--no-ytdl"]
            cmd += [f"--referrer={referer}"]
            cmd += [f"--http-header-fields=Origin: {origin}"]
        else:
            cmd += ["--referrer=https://cloudnestra.com/"]
            cmd += ["--http-header-fields=Origin: https://cloudnestra.com"]

        # HLS reliability: cache + aggressive reconnect (survives 429 / segment errors)
        cmd += [
            "--cache=yes",
            "--demuxer-max-bytes=32M",
            "--demuxer-max-back-bytes=10M",
            "--stream-lavf-o=reconnect_on_http_error=4xx,5xx,reconnect_delay_max=5",
            "--demuxer-lavf-o=http_persistent=0"
        ]

        if audio_track is not None: 
            cmd += [f"--aid={audio_track}"]
        elif audio_lang:            
            cmd += [f"--alang={audio_lang}"]

        if sub_path and (sub_path.startswith("http") or os.path.exists(sub_path)):
            cmd += [f"--sub-file={sub_path}"]
            if sub_track is None: cmd += ["--sid=1"]
            else: cmd += [f"--sid={sub_track}"]
        elif sub_track is not None: 
            cmd += [f"--sid={sub_track}"]
        elif sub_lang == "off":     
            cmd += ["--no-sub"]
        elif sub_lang:              
            cmd += [f"--slang={sub_lang}"]

        if player_args:
            cmd += player_args.split()

        cmd.append(stream_url)
        
        try:
            subprocess.run(cmd)
        except FileNotFoundError:
            warn(f"Le lecteur {player} n'est pas installé ou introuvable.")
        except Exception as e:
            warn(f"Erreur lors de la lecture: {e}")
    else:
        warn(f"Lecteur non supporté de manière optimale : {player}")
        cmd = [player]
        if player_args: cmd += player_args.split()
        cmd.append(stream_url)
        subprocess.run(cmd)
