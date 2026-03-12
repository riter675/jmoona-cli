"""
extractor.py — Extraction pipeline for jmoona-cli v1.0.4

Phase -1 : IMDB-ID providers      (curl_cffi impersonation, for rare content)
Phase  0 : Cloudnestra HTTP        (vidsrc.to → vsembed.ru → cloudnestra.com)
Phase  1 : curl_cffi HTTP scrapers (vidsrc.cc, embed.su, superembed, videasy…)
Phase  2a: Selenium Cloudnestra    (Chromium headless, bypasses Turnstile)
Phase  2b: Selenium VidLink        (vidlink.pro)
Phase  3 : yt-dlp quick            (top 6 providers)
Phase  4 : yt-dlp exhaustive       (all remaining providers)
Phase  5 : yt-dlp with spoofed referer on IMDB providers (last resort)
"""
import os, re, json, subprocess, shutil, urllib.request, urllib.parse, time
import threading
from .config import UA
from .providers import PROVIDERS, IMDB_PROVIDERS
from .ui import spinner, clear_line, success, warn

# ─────────────────────────────────────────────────────────────────────────────
# Dependency detection
# ─────────────────────────────────────────────────────────────────────────────

def _uc_ok():
    try: import undetected_chromedriver; return True
    except: return False

def selenium_ok():
    try: import selenium; return True
    except: return False

def chromedriver_path():
    local = os.path.expanduser("~/.local/bin/chromedriver")
    if os.path.exists(local): return local
    for p in ["chromedriver", "chromium-driver", "chromium.chromedriver"]:
        found = shutil.which(p)
        if found: return found
    for p in ["/usr/bin/chromedriver", "/usr/lib/chromium/chromedriver",
              "/usr/lib/chromium-browser/chromedriver"]:
        if os.path.exists(p): return p
    return None

def ytdlp_ok():
    if shutil.which("yt-dlp") is not None:
        return True
    try:
        res = subprocess.run(
            ["python", "-m", "yt_dlp", "--version"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5
        )
        return res.returncode == 0
    except Exception:
        return False

def cffi_ok():
    try: from curl_cffi import requests as _; return True
    except: return False

# ─────────────────────────────────────────────────────────────────────────────
# HTTP helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get(url, referer=None, timeout=10, extra_headers=None):
    """Simple urllib request."""
    try:
        headers = {"User-Agent": UA}
        if referer:
            headers["Referer"] = referer
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except:
        return None


def _cffi_get(url, referer=None, timeout=12, extra_headers=None):
    """curl_cffi impersonating Chrome — bypasses Cloudflare & TLS fingerprinting."""
    if not cffi_ok():
        return _get(url, referer=referer, timeout=timeout, extra_headers=extra_headers)
    try:
        from curl_cffi import requests as cr
        h = {"Referer": referer} if referer else {}
        if extra_headers:
            h.update(extra_headers)
        resp = cr.get(url, impersonate="chrome", headers=h, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200:
            return resp.text
    except:
        pass
    return None

# ─────────────────────────────────────────────────────────────────────────────
# Selenium helper
# ─────────────────────────────────────────────────────────────────────────────

def _selenium_rcp(rcp_url, referer="https://vsembed.ru/", timeout=30):
    """Drive Chromium to a cloudnestra/rcp URL and intercept the m3u8."""
    driver_path = chromedriver_path()
    if not driver_path:
        return None, None
    driver = None
    disp   = None
    try:
        if _uc_ok():
            import undetected_chromedriver as uc
            try:
                from pyvirtualdisplay import Display
                disp = Display(visible=0, size=(1920, 1080))
                disp.start()
            except ImportError:
                disp = None

            opts = uc.ChromeOptions()
            opts.add_argument("--mute-audio")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})
            driver = uc.Chrome(options=opts, version_main=145,
                               driver_executable_path=driver_path)
        elif selenium_ok():
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            opts = Options()
            opts.add_argument("--headless=new")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-gpu")
            opts.add_argument(f"--user-agent={UA}")
            opts.add_argument("--mute-audio")
            opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            driver = webdriver.Chrome(
                service=Service(driver_path, log_path=os.devnull),
                options=opts
            )
        else:
            return None, None

        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd("Network.setExtraHTTPHeaders",
                               {"headers": {"Referer": referer}})
        driver.get(rcp_url)

        for _ in range(15):
            time.sleep(2)
            try:
                if "cf-turnstile" not in driver.page_source:
                    break
            except Exception:
                pass

        time.sleep(2)
        try:
            driver.execute_script(
                "document.querySelector('#pl_but_background,#pl_but,button')?.click();"
                "if(typeof loadIframe=='function') loadIframe(1);"
            )
        except Exception:
            pass

        time.sleep(10)

        found = None
        for log in driver.get_log("performance"):
            try:
                url = json.loads(log["message"])["message"]["params"]["request"]["url"]
                if "tmstr" in url and "/pl/" in url and "master.m3u8" in url:
                    found = url; break
                elif "tmstr" in url and "/pl/" in url and not found:
                    found = url
            except:
                pass

        driver.quit()
        if disp:
            try: disp.stop()
            except: pass
        return found, None

    except Exception as e:
        warn(f"Selenium erreur: {e}")
        try: driver.quit()
        except: pass
        if disp:
            try: disp.stop()
            except: pass
        return None, None

# ─────────────────────────────────────────────────────────────────────────────
# Main extract() entry-point
# ─────────────────────────────────────────────────────────────────────────────

def extract(tmdb_id, media_type, season=1, episode=1,
            quality="best", lang="fr", proxy=None, provider="auto",
            imdb_id=None):
    """
    Try every extraction strategy in order and return (stream_url, vtt_url).
    Returns (None, None) if everything fails.

    Phase -1: curl_cffi on IMDB-ID providers (for rare content)
    Phase  0: Cloudnestra HTTP
    Phase  1: curl_cffi scrapers on all TMDB providers
    Phase 2a: Selenium Cloudnestra
    Phase 2b: Selenium VidLink
    Phase  3: yt-dlp quick (top 6)
    Phase  4: yt-dlp exhaustive (rest)
    Phase  5: yt-dlp on IMDB providers with spoofed referer
    """
    providers = PROVIDERS
    if provider != "auto":
        filtered = [p for p in PROVIDERS if provider.lower() in p[0].lower()]
        providers = filtered or PROVIDERS

    def _tpl(movie_t, tv_t):
        tpl = movie_t if media_type == "movie" else tv_t
        return tpl.format(id=tmdb_id, s=season, e=episode,
                          imdb=imdb_id or "")

    def _tpl_imdb(movie_t, tv_t):
        if not imdb_id:
            return None
        tpl = movie_t if media_type == "movie" else tv_t
        return tpl.format(id=tmdb_id, s=season, e=episode,
                          imdb=imdb_id.lstrip("t"))

    # ── regex patterns ────────────────────────────────────────────────────────
    _STREAM_RE = re.compile(
        r'(?:file|src|source|url)\s*[=:]\s*["\']'
        r'(https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)',
        re.IGNORECASE
    )
    _HLS_RE = re.compile(r'(https?://[^"\'<>\s]+\.m3u8[^"\'<>\s]*)', re.IGNORECASE)
    _MP4_RE = re.compile(r'(https?://[^"\'<>\s]+\.mp4[^"\'<>\s]*)', re.IGNORECASE)

    def _extract_from_html(html, embed_url):
        if not html:
            return None, None
        for pattern in (_STREAM_RE, _HLS_RE, _MP4_RE):
            m = pattern.search(html)
            if m:
                return m.group(1), None
        # iframe redirect — follow one level
        iframe = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if iframe:
            iframe_url = iframe.group(1)
            if not iframe_url.startswith("http") and not iframe_url.startswith("//"):
                iframe_url = urllib.parse.urljoin(embed_url, iframe_url)
            elif iframe_url.startswith("//"):
                iframe_url = "https:" + iframe_url

            # Fast track famous hosts to yt-dlp directly instead of naive regex
            known_hosts = ["dood", "streamtape", "voe", "upstream", "mixdrop", "filemoon", "vudeo", "vidhide", "uqload"]
            if any(h in iframe_url for h in known_hosts):
                url, vtt = _ytdlp(iframe_url, quality=quality, referer=embed_url)
                if url: return url, vtt

            html2 = _cffi_get(iframe_url, referer=embed_url)
            if html2:
                for pattern in (_STREAM_RE, _HLS_RE, _MP4_RE):
                    m = pattern.search(html2)
                    if m:
                        return m.group(1), None
        return None, None

    def _scrape(embed_url, referer="https://www.google.com/"):
        html = _cffi_get(embed_url, referer=referer)
        return _extract_from_html(html, embed_url)

    # ── Phase -1: IMDB-ID providers (rare content) ────────────────────────────

    def _phase_minus1():
        if not imdb_id:
            return None, None
        for name, movie_t, tv_t in IMDB_PROVIDERS:
            embed = _tpl_imdb(movie_t, tv_t)
            if not embed:
                continue
            url, vtt = _scrape(embed, referer="https://www.google.com/")
            if url:
                return url, vtt
        return None, None

    # ── Phase 0: Cloudnestra HTTP ─────────────────────────────────────────────

    def _cloudnestra():
        if media_type == "movie":
            vt_url = f"https://vidsrc.to/embed/movie/{tmdb_id}"
        else:
            vt_url = f"https://vidsrc.to/embed/tv/{tmdb_id}/{season}/{episode}"

        html1 = _cffi_get(vt_url, referer="https://vidsrc.to/")
        m = re.search(r'src="((?:https?:)?//vsembed\.ru/embed/[^"]+)"', html1 or "")
        if not m: return None, None
        vs_url = m.group(1)
        if vs_url.startswith("//"): vs_url = "https:" + vs_url

        html2 = _cffi_get(vs_url, referer="https://vidsrc.to/")
        hashes = re.findall(r'data-hash="([^"]+)"', html2 or "")
        if not hashes: return None, None

        for h in hashes:
            rcp_url = f"https://cloudnestra.com/rcp/{h}"
            html3 = _cffi_get(rcp_url, referer="https://vsembed.ru/")
            if not html3: continue
            if "turnstile" in html3: continue

            m = re.search(r"src:\s*'/prorcp/([^']+)'", html3)
            if not m: continue
            prorcp_hash = m.group(1)

            prorcp_url = f"https://cloudnestra.com/prorcp/{prorcp_hash}"
            html4 = _cffi_get(prorcp_url, referer=rcp_url)
            if not html4: continue

            m = re.search(
                r'(?:tmstr1\.\{v1\}|tmstr1\.[a-z0-9\-\.]+)/pl/([^"\'<> ]+(?:master\.m3u8|\.m3u8))',
                html4
            )
            if not m: continue
            m3u8_path = m.group(1)

            domains = re.findall(
                r'tmstr1\.([a-z][a-z0-9\-]*(?:\.[a-z0-9\-]+){1,3})',
                html4
            )
            for domain in domains[:6]:
                url = f"https://tmstr1.{domain}/pl/{m3u8_path}"
                try:
                    req = urllib.request.Request(url, headers={
                        "User-Agent": UA, "Referer": "https://cloudnestra.com/"
                    })
                    with urllib.request.urlopen(req, timeout=8) as r:
                        if r.status == 200:
                            return url, None
                except:
                    continue
        return None, None

    # ── Phase 1: curl_cffi scrapers ───────────────────────────────────────────

    def _scrape_provider(name, movie_t, tv_t):
        embed = _tpl(movie_t, tv_t)
        return _scrape(embed, referer="https://www.google.com/")

    # ── Phase 2a: Selenium Cloudnestra ────────────────────────────────────────

    def _selenium_via_cloudnestra(timeout=30):
        if media_type == "movie":
            vt_url = f"https://vidsrc.to/embed/movie/{tmdb_id}"
        else:
            vt_url = f"https://vidsrc.to/embed/tv/{tmdb_id}/{season}/{episode}"

        html1 = _cffi_get(vt_url, referer="https://vidsrc.to/")
        m = re.search(r'src="((?:https?:)?//vsembed\.ru/embed/[^"]+)"', html1 or "")
        if not m: return None, None
        vs_url = m.group(1)
        if vs_url.startswith("//"): vs_url = "https:" + vs_url

        html2 = _cffi_get(vs_url, referer="https://vidsrc.to/")
        hashes = re.findall(r'data-hash="([^"]+)"', html2 or "")
        if not hashes: return None, None

        rcp_url = f"https://cloudnestra.com/rcp/{hashes[0]}"
        return _selenium_rcp(rcp_url, referer="https://vsembed.ru/", timeout=timeout)

    # ── Phase 2b: Selenium VidLink ────────────────────────────────────────────

    def _selenium_vidlink(timeout=20):
        driver_path = chromedriver_path()
        if not driver_path or not _uc_ok():
            return None, None

        url = (f"https://vidlink.pro/movie/{tmdb_id}" if media_type == "movie"
               else f"https://vidlink.pro/tv/{tmdb_id}/{season}/{episode}")

        driver = None
        disp   = None
        try:
            import undetected_chromedriver as uc
            try:
                from pyvirtualdisplay import Display
                disp = Display(visible=0, size=(1920, 1080))
                disp.start()
            except ImportError:
                disp = None

            opts = uc.ChromeOptions()
            opts.add_argument("--mute-audio")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})
            driver = uc.Chrome(options=opts, version_main=145,
                               driver_executable_path=driver_path)

            driver.execute_cdp_cmd("Network.enable", {})
            driver.get(url)
            time.sleep(12)

            m3u8 = None
            vtt  = None
            referer = "https://videostr.net/"
            origin  = "https://videostr.net"

            for log in driver.get_log("performance"):
                try:
                    req_url = json.loads(log["message"])["message"]["params"]["request"]["url"]
                    if ".m3u8" in req_url and "proxy" in req_url and not m3u8:
                        m3u8 = req_url
                        qs = urllib.parse.parse_qs(urllib.parse.urlparse(req_url).query)
                        if "headers" in qs:
                            hdict = json.loads(qs["headers"][0])
                            referer = hdict.get("referer", referer)
                            origin  = hdict.get("origin",  origin)
                    elif ".vtt" in req_url and not vtt:
                        vtt = req_url
                except:
                    pass

            driver.quit()
            if disp:
                try: disp.stop()
                except: pass

            if m3u8:
                try:
                    from curl_cffi import requests as cffi_requests
                    resp = cffi_requests.get(
                        m3u8,
                        impersonate="chrome",
                        headers={"Referer": referer, "Origin": origin},
                        allow_redirects=True,
                        timeout=15
                    )
                    if resp.status_code == 200:
                        content = resp.text
                        final   = str(resp.url)
                        lines   = [l.strip() for l in content.splitlines()
                                   if l.strip() and not l.startswith("#")]
                        if lines:
                            m3u8 = urllib.parse.urljoin(final, lines[-1])
                        else:
                            m3u8 = final
                except Exception:
                    pass

            return m3u8, vtt

        except Exception as e:
            warn(f"VidLink Selenium erreur: {e}")
            try: driver.quit()
            except: pass
            if disp:
                try: disp.stop()
                except: pass
            return None, None

    # ── Phase 3 / 4 / 5: yt-dlp ──────────────────────────────────────────────

    def _ytdlp(embed_url, quality="best", referer=None):
        """Extract stream URL via yt-dlp. Tries binary then python -m fallback."""
        base_args = ["-g", "--no-warnings", "--no-playlist"]
        if referer:
            base_args += ["--referer", referer,
                          "--add-header", f"Referer:{referer}"]
        cmds = []
        if shutil.which("yt-dlp"):
            cmds.append(["yt-dlp"] + base_args + [embed_url])
        cmds.append(["python", "-m", "yt_dlp"] + base_args + [embed_url])
        for cmd in cmds:
            try:
                res = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, timeout=30
                )
                if res.returncode == 0 and res.stdout.strip():
                    lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
                    if lines:
                        return lines[0], None
            except Exception:
                continue
        return None, None

    # ── Concurrent helper for phase 1 ─────────────────────────────────────────

    def _scrape_concurrent(provider_list, max_workers=10):
        """Try multiple providers concurrently, return first success."""
        result = [None, None]
        stop = threading.Event()

        def worker(name, movie_t, tv_t):
            if stop.is_set():
                return
            url, vtt = _scrape_provider(name, movie_t, tv_t)
            if url and not stop.is_set():
                result[0] = url
                result[1] = vtt
                stop.set()

        threads = []
        for chunk_start in range(0, len(provider_list), max_workers):
            chunk = provider_list[chunk_start:chunk_start + max_workers]
            threads = [threading.Thread(target=worker, args=p, daemon=True) for p in chunk]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=15)
            if result[0]:
                return result[0], result[1]
        return None, None

    # ── Execution pipeline ─────────────────────────────────────────────────────

    from .art import get_random_art

    # Fetch IMDB ID once for phases that need it
    _cached_imdb = imdb_id
    def _get_imdb():
        nonlocal _cached_imdb
        if _cached_imdb:
            return _cached_imdb
        try:
            from .tmdb import tmdb_client
            _cached_imdb = tmdb_client.imdb_id(tmdb_id, media_type)
        except Exception:
            pass
        return _cached_imdb

    # Phase -1
    iid = _get_imdb()
    if iid:
        spinner("🔍 Recherche via ID IMDB (titres rares) ...", art=get_random_art())
        url, vtt = _phase_minus1()
        if url:
            clear_line(); success("Stream trouvé via ID IMDB"); return url, vtt
        clear_line()

    # Phase 0
    spinner("🔍 Cloudnestra HTTP ...", art=get_random_art())
    url, vtt = _cloudnestra()
    if url:
        clear_line(); success("Stream trouvé via Cloudnestra"); return url, vtt
    clear_line()

    # Phase 1 (concurrent, max 10 at a time)
    spinner(f"🔍 Scrapers HTTP ({len(providers)} providers) ...", art=get_random_art())
    url, vtt = _scrape_concurrent(providers, max_workers=10)
    if url:
        clear_line(); success("Stream trouvé via scraper HTTP"); return url, vtt
    clear_line()

    # Phase 2a
    if chromedriver_path():
        warn("Lancement Chromium (Cloudnestra) ...")
        url, vtt = _selenium_via_cloudnestra()
        if url:
            clear_line(); success("Stream intercepté via Chromium / Cloudnestra")
            return url, vtt
        clear_line()

        # Phase 2b
        if _uc_ok():
            warn("Lancement Chromium (VidLink) ...")
            url, vtt = _selenium_vidlink()
            if url:
                clear_line(); success("Stream intercepté via Chromium / VidLink")
                return url, vtt
            clear_line()

    # Phase 3
    if ytdlp_ok():
        warn("Tentative yt-dlp (providers prioritaires) ...")
        for name, movie_t, tv_t in providers[:6]:
            embed_url = _tpl(movie_t, tv_t)
            url, vtt = _ytdlp(embed_url, quality=quality)
            if url:
                clear_line(); success(f"Stream via yt-dlp ({name})")
                return url, vtt
        clear_line()

        # Phase 4
        warn("Tentative yt-dlp (tous les providers) ...")
        for name, movie_t, tv_t in providers[6:]:
            embed_url = _tpl(movie_t, tv_t)
            url, vtt = _ytdlp(embed_url, quality=quality)
            if url:
                clear_line(); success(f"Stream via yt-dlp ({name})")
                return url, vtt
        clear_line()

        # Phase 5 — yt-dlp on IMDB-based providers
        iid = _get_imdb()
        if iid:
            warn("Tentative yt-dlp (providers IMDB) ...")
            for name, movie_t, tv_t in IMDB_PROVIDERS:
                embed_url = _tpl_imdb(movie_t, tv_t)
                if not embed_url:
                    continue
                url, vtt = _ytdlp(embed_url, quality=quality,
                                  referer="https://www.google.com/")
                if url:
                    clear_line(); success(f"Stream via yt-dlp IMDB ({name})")
                    return url, vtt
            clear_line()

    warn("Aucun flux trouvé. Vérifie ta connexion ou essaie un autre titre.")
    return None, None
