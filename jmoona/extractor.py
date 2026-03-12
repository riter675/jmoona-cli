import os, re, json, subprocess, shutil, urllib.request, urllib.parse, time
from .config import UA
from .providers import PROVIDERS
from .ui import spinner, clear_line, success, warn

# ─────────────────────────────────────────────────────────────────────────────
# Helpers: dependency detection
# ─────────────────────────────────────────────────────────────────────────────

def _uc_ok():
    try: import undetected_chromedriver; return True
    except: return False

def selenium_ok():
    try: import selenium; return True
    except: return False

def chromedriver_path():
    """Return the first usable chromedriver binary path, or None."""
    # Prefer a user-writable copy (undetected-chromedriver must patch it)
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
    """True if yt-dlp is usable (CLI binary OR python -m yt_dlp)."""
    if shutil.which("yt-dlp") is not None:
        return True
    # Fallback: installed via pip but not in PATH (common on Windows / macOS)
    try:
        res = subprocess.run(
            ["python", "-m", "yt_dlp", "--version"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5
        )
        return res.returncode == 0
    except Exception:
        return False

# ─────────────────────────────────────────────────────────────────────────────
# Low-level HTTP helper
# ─────────────────────────────────────────────────────────────────────────────

def _get(url, referer=None, timeout=10):
    try:
        headers = {"User-Agent": UA}
        if referer:
            headers["Referer"] = referer
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except:
        return None

# ─────────────────────────────────────────────────────────────────────────────
# Selenium helper — shared by cloudnestra & vidlink paths
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
            # pyvirtualdisplay lets UC run without a real framebuffer (Linux CI/headless)
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
                # os.devnull is cross-platform (/dev/null on Unix, NUL on Windows)
                service=Service(driver_path, log_path=os.devnull),
                options=opts
            )
        else:
            return None, None

        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd("Network.setExtraHTTPHeaders",
                               {"headers": {"Referer": referer}})
        driver.get(rcp_url)

        # Wait for Cloudflare Turnstile to auto-solve (~8–15 s with UC)
        for _ in range(15):
            time.sleep(2)
            try:
                if "cf-turnstile" not in driver.page_source:
                    break
            except Exception:
                pass

        # Give the page an extra moment, then trigger playback
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
            quality="best", lang="fr", proxy=None, provider="auto"):
    """
    Try every extraction strategy in order and return (stream_url, vtt_url).
    Returns (None, None) if everything fails.

    Phase 0 : Cloudnestra HTTP  (vidsrc.to → vsembed.ru → cloudnestra.com)
    Phase 1 : Scrapers HTTP      (vidsrc.cc, embed.su, …)
    Phase 2a: Selenium Cloudnestra (Chromium headless, bypasses Turnstile)
    Phase 2b: Selenium VidLink   (vidlink.pro, curl_cffi to resolve proxy)
    Phase 3 : yt-dlp quick       (top 4 providers)
    Phase 4 : yt-dlp exhaustive  (all providers, last resort)
    """
    providers = PROVIDERS
    if provider != "auto":
        filtered = [p for p in PROVIDERS if provider.lower() in p[0].lower()]
        providers = filtered or PROVIDERS

    # ── helpers ───────────────────────────────────────────────────────────────

    def _tpl(movie_t, tv_t):
        """Pick movie or TV template and fill it."""
        tpl = movie_t if media_type == "movie" else tv_t
        return tpl.format(id=tmdb_id, s=season, e=episode)

    def _embed_url(name):
        for n, mt, tt in providers:
            if n == name:
                return _tpl(mt, tt)
        return None

    # ── Phase 0: Cloudnestra HTTP ─────────────────────────────────────────────

    def _cloudnestra():
        if media_type == "movie":
            vt_url = f"https://vidsrc.to/embed/movie/{tmdb_id}"
        else:
            vt_url = f"https://vidsrc.to/embed/tv/{tmdb_id}/{season}/{episode}"

        html1 = _get(vt_url, referer="https://vidsrc.to/")
        m = re.search(r'src="((?:https?:)?//vsembed\.ru/embed/[^"]+)"', html1 or "")
        if not m: return None, None
        vs_url = m.group(1)
        if vs_url.startswith("//"): vs_url = "https:" + vs_url

        html2 = _get(vs_url, referer="https://vidsrc.to/")
        hashes = re.findall(r'data-hash="([^"]+)"', html2 or "")
        if not hashes: return None, None

        for h in hashes:
            rcp_url = f"https://cloudnestra.com/rcp/{h}"
            html3 = _get(rcp_url, referer="https://vsembed.ru/")
            if not html3: continue
            if "turnstile" in html3: continue  # needs Selenium — skip to Phase 2

            m = re.search(r"src:\s*'/prorcp/([^']+)'", html3)
            if not m: continue
            prorcp_hash = m.group(1)

            prorcp_url = f"https://cloudnestra.com/prorcp/{prorcp_hash}"
            html4 = _get(prorcp_url, referer=rcp_url)
            if not html4: continue

            # Accept both "{v1}" placeholder and literal domain references
            m = re.search(
                r'(?:tmstr1\.\{v1\}|tmstr1\.[a-z0-9\-\.]+)/pl/([^"\'<> ]+(?:master\.m3u8|\.m3u8))',
                html4
            )
            if not m: continue
            m3u8_path = m.group(1)

            # Broader domain pattern: allow 2-level and 3-level TLDs
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

    # ── Phase 1: HTTP scrapers ────────────────────────────────────────────────

    # Regex patterns to search for a playable stream URL inside provider HTML
    _STREAM_RE = re.compile(
        r'(?:file|src|source|url)\s*[=:]\s*["\']'
        r'(https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)',
        re.IGNORECASE
    )
    _HLS_RE = re.compile(r'(https?://[^"\'<>\s]+\.m3u8[^"\'<>\s]*)', re.IGNORECASE)
    _MP4_RE = re.compile(r'(https?://[^"\'<>\s]+\.mp4[^"\'<>\s]*)', re.IGNORECASE)

    def _scrape_provider(name, movie_t, tv_t):
        embed = _tpl(movie_t, tv_t)
        html = _get(embed, referer="https://www.google.com/")
        if not html:
            return None, None

        # 1. Named pattern (file:'…', src='…', etc.)
        m = _STREAM_RE.search(html)
        if m:
            return m.group(1), None

        # 2. Bare HLS URL anywhere in the page
        m = _HLS_RE.search(html)
        if m:
            return m.group(1), None

        # 3. Bare MP4 URL anywhere
        m = _MP4_RE.search(html)
        if m:
            return m.group(1), None

        # 4. iframe redirect — follow one level
        iframe = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if iframe:
            iframe_url = iframe.group(1)
            if not iframe_url.startswith("http"):
                iframe_url = urllib.parse.urljoin(embed, iframe_url)
            html2 = _get(iframe_url, referer=embed)
            if html2:
                for pattern in (_STREAM_RE, _HLS_RE, _MP4_RE):
                    m = pattern.search(html2)
                    if m:
                        return m.group(1), None

        return None, None

    # ── Phase 2a: Selenium via Cloudnestra ───────────────────────────────────

    def _selenium_via_cloudnestra(timeout=30):
        if media_type == "movie":
            vt_url = f"https://vidsrc.to/embed/movie/{tmdb_id}"
        else:
            vt_url = f"https://vidsrc.to/embed/tv/{tmdb_id}/{season}/{episode}"

        html1 = _get(vt_url, referer="https://vidsrc.to/")
        m = re.search(r'src="((?:https?:)?//vsembed\.ru/embed/[^"]+)"', html1 or "")
        if not m: return None, None
        vs_url = m.group(1)
        if vs_url.startswith("//"): vs_url = "https:" + vs_url

        html2 = _get(vs_url, referer="https://vidsrc.to/")
        hashes = re.findall(r'data-hash="([^"]+)"', html2 or "")
        if not hashes: return None, None

        rcp_url = f"https://cloudnestra.com/rcp/{hashes[0]}"
        return _selenium_rcp(rcp_url, referer="https://vsembed.ru/", timeout=timeout)

    # ── Phase 2b: Selenium via VidLink ───────────────────────────────────────

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

            # Resolve proxy URL → direct CDN URL via curl_cffi
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
                    pass  # keep the proxy URL as fallback

            return m3u8, vtt

        except Exception as e:
            warn(f"VidLink Selenium erreur: {e}")
            try: driver.quit()
            except: pass
            if disp:
                try: disp.stop()
                except: pass
            return None, None

    # ── Phase 3 / 4: yt-dlp ─────────────────────────────────────────────────

    def _ytdlp(embed_url, quality="best"):
        """Extract stream URL via yt-dlp. Tries binary then python -m fallback."""
        cmds = []
        if shutil.which("yt-dlp"):
            cmds.append(["yt-dlp", "-g", "--no-warnings", "--no-playlist", embed_url])
        cmds.append(["python", "-m", "yt_dlp", "-g", "--no-warnings",
                     "--no-playlist", embed_url])
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

    # ── Execution pipeline ────────────────────────────────────────────────────

    from .art import get_random_art

    # Phase 0
    spinner("🔍 Cloudnestra HTTP ...", art=get_random_art())
    url, vtt = _cloudnestra()
    if url:
        clear_line(); success("Stream trouvé via Cloudnestra"); return url, vtt
    clear_line()

    # Phase 1
    for i, (name, movie_t, tv_t) in enumerate(providers, 1):
        spinner(f"🔍 Provider [{i}/{len(providers)}] {name} ...", art=get_random_art())
        url, vtt = _scrape_provider(name, movie_t, tv_t)
        if url:
            clear_line(); success(f"Stream trouvé via {name}"); return url, vtt
    clear_line()

    # Phase 2a
    if chromedriver_path():
        warn("Lancement Chromium (Cloudnestra) ...")
        url, vtt = _selenium_via_cloudnestra()
        if url:
            clear_line(); success("Stream intercepté via Chromium / Cloudnestra")
            return url, vtt
        clear_line()

        # Phase 2b — VidLink (only if undetected-chromedriver available)
        if _uc_ok():
            warn("Lancement Chromium (VidLink) ...")
            url, vtt = _selenium_vidlink()
            if url:
                clear_line(); success("Stream intercepté via Chromium / VidLink")
                return url, vtt
            clear_line()

    # Phase 3 — yt-dlp quick (top 4 providers)
    if ytdlp_ok():
        warn("Tentative yt-dlp (providers prioritaires) ...")
        for name, movie_t, tv_t in providers[:4]:
            embed_url = _tpl(movie_t, tv_t)
            url, vtt = _ytdlp(embed_url, quality=quality)
            if url:
                clear_line(); success(f"Stream via yt-dlp ({name})")
                return url, vtt
        clear_line()

        # Phase 4 — yt-dlp exhaustive
        warn("Tentative yt-dlp (tous les providers) ...")
        for name, movie_t, tv_t in providers[4:]:
            embed_url = _tpl(movie_t, tv_t)
            url, vtt = _ytdlp(embed_url, quality=quality)
            if url:
                clear_line(); success(f"Stream via yt-dlp ({name})")
                return url, vtt
        clear_line()

    warn("Aucun flux trouvé. Vérifie ta connexion ou essaie un autre titre.")
    return None, None
