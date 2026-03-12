import subprocess
import json

LANG_MAP = {
    "fr": ["French", "Français", "fr", "fre", "fra"],
    "en": ["English", "Anglais", "en", "eng"],
    "ja": ["Japanese", "Japonais", "ja", "jpn"],
    "ko": ["Korean", "Coréen", "ko", "kor"],
    "es": ["Spanish", "Espagnol", "es", "spa"],
    "de": ["German", "Allemand", "de", "deu", "ger"],
    "it": ["Italian", "Italien", "it", "ita"],
    "pt": ["Portuguese", "Portugais", "pt", "por"],
    "ar": ["Arabic", "Arabe", "ar", "ara"],
    "zh": ["Chinese", "Chinois", "zh", "zho", "chi"],
    "hi": ["Hindi", "hi", "hin"],
    "ru": ["Russian", "Russe", "ru", "rus"],
}

def normalize_lang(lang_code_or_name):
    lang_lower = lang_code_or_name.lower()
    for code, aliases in LANG_MAP.items():
        if lang_lower in [a.lower() for a in aliases]:
            return code
    return lang_lower

def get_lang_label(lang_code):
    norm = normalize_lang(lang_code)
    return LANG_MAP.get(norm, [norm])[0] if norm in LANG_MAP else lang_code

def detect_tracks(stream_url: str) -> dict:
    from .config import UA
    import urllib.parse
    
    parsed = urllib.parse.urlparse(stream_url)
    referer = "https://cloudnestra.com/"
    origin = "https://cloudnestra.com"
    
    if "headers=" in stream_url:
        import json
        try:
            qs = urllib.parse.parse_qs(parsed.query)
            if "headers" in qs:
                hdict = json.loads(qs["headers"][0])
                referer = hdict.get("referer", referer)
                origin = hdict.get("origin", origin)
        except: pass

    headers = f"User-Agent: {UA}\r\nReferer: {referer}\r\nOrigin: {origin}\r\n"
    cmd = ["ffprobe", "-headers", headers, "-v", "quiet", "-print_format", "json",
           "-show_streams", stream_url]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
        if result.returncode != 0:
            return {"audio": [], "subs": []}
        data = json.loads(result.stdout)
    except Exception:
        return {"audio": [], "subs": []}

    tracks = {"audio": [], "subs": []}
    seen_audio_langs = set()
    audio_idx = 1
    sub_idx = 1
    
    for stream in data.get("streams", []):
        codec_type = stream.get("codec_type")
        tags = stream.get("tags", {})
        lang = tags.get("language", "und")
        
        if codec_type == "audio":
            norm_lang = normalize_lang(lang)
            # Avoid grouping multiple audio streams of the same language (e.g., from different M3U8 quality variants)
            if norm_lang not in seen_audio_langs:
                seen_audio_langs.add(norm_lang)
                tracks["audio"].append({
                    "index": stream.get("index"),
                    "mpv_id": audio_idx,
                    "lang": norm_lang,
                    "original_lang": lang,
                    "codec": stream.get("codec_name", "unknown"),
                    "channels": stream.get("channels", 2)
                })
            audio_idx += 1
            
        elif codec_type == "subtitle":
            tracks["subs"].append({
                "index": stream.get("index"),
                "mpv_id": sub_idx,
                "lang": normalize_lang(lang),
                "original_lang": lang,
                "format": stream.get("codec_name", "unknown")
            })
            sub_idx += 1

    return tracks
