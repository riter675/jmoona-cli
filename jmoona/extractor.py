import os, re, json, subprocess, shutil, urllib.request, urllib.parse, time
from .config import UA
from .providers import PROVIDERS
from .ui import spinner, clear_line, success, warn

def _uc_ok():
    try: import undetected_chromedriver; return True
    except: return False

def selenium_ok():
    try: import selenium; return True
    except: return False

def chromedriver_path():
    local = os.path.expanduser("~/.local/bin/chromedriver")
    if os.path.exists(local): return local
    for p in ["chromedriver", "chromium-driver"]:
        found = shutil.which(p)
        if found: return found
    for p in ["/usr/bin/chromedriver", "/usr/lib/chromium/chromedriver"]:
        if os.path.exists(p): return p
    return None

def ytdlp_ok():
    return shutil.which("yt-dlp") is not None

def _get(url, referer=None):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        if referer: req.add_header("Referer", referer)
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode("utf-8", errors="ignore")
    except: return None

def _selenium_rcp(rcp_url, referer="https://vsembed.ru/", timeout=30):
    driver_path = chromedriver_path()
    if not driver_path: return None
    driver = None
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
                service=Service(driver_path, log_path="/dev/null"), options=opts
            )
        else:
            return None

        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd("Network.setExtraHTTPHeaders",
                               {"headers": {"Referer": referer}})
        driver.get(rcp_url)

        # Wait for Turnstile to solve and page to reload automatically
        for _ in range(15):
            time.sleep(2)
            try:
                if 'cf-turnstile' not in driver.page_source:
                    break
            except Exception:
                pass

        time.sleep(2) # Give it an extra moment to settle
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
            except: pass

        driver.quit()
        try:
            if 'disp' in locals() and disp: disp.stop()
        except: pass
        return found, None
    except Exception as e:
        warn(f"Selenium erreur: {e}")
        try: driver.quit()
        except: pass
        try:
            if 'disp' in locals() and disp: disp.stop()
        except: pass
        return None, None

def extract(tmdb_id, media_type, season=1, episode=1,
            quality="best", lang="fr", proxy=None, provider="auto"):
    
    providers = PROVIDERS
    if provider != "auto":
        providers = [p for p in PROVIDERS if provider.lower() in p[0].lower()] or PROVIDERS

    def _cloudnestra(tmdb_id, media_type, season=1, episode=1):
        if media_type == "movie":
            vt_url = f"https://vidsrc.to/embed/movie/{tmdb_id}"
        else:
            vt_url = f"https://vidsrc.to/embed/tv/{tmdb_id}/{season}/{episode}"

        html1 = _get(vt_url, referer="https://vidsrc.to/")
        m = re.search(r'src="((?:https?:)?//vsembed\.ru/embed/[^"]+)"', html1 or "")
        if not m: return None
        vs_url = m.group(1)
        if vs_url.startswith('//'): vs_url = 'https:' + vs_url

        html2 = _get(vs_url, referer="https://vidsrc.to/")
        hashes = re.findall(r'data-hash="([^"]+)"', html2 or "")
        if not hashes: return None

        for h in hashes:
            rcp_url = f"https://cloudnestra.com/rcp/{h}"
            html3 = _get(rcp_url, referer="https://vsembed.ru/")
            if not html3: continue
            if "turnstile" in html3: continue

            m = re.search(r"src:\s*'/prorcp/([^']+)'", html3)
            if not m: continue
            prorcp_hash = m.group(1)

            prorcp_url = f"https://cloudnestra.com/prorcp/{prorcp_hash}"
            html4 = _get(prorcp_url, referer=rcp_url)
            if not html4: continue

            m = re.search(r'tmstr1\.\{v1\}/pl/([^"\'<> ]+master\.m3u8)', html4)
            if not m: continue
            m3u8_path = m.group(1)

            domains = re.findall(r'tmstr1\.([a-z][a-z0-9\-]+\.[a-z0-9\-]+\.[a-z]{2,})', html4)
            for domain in domains[:4]:
                url = f"https://tmstr1.{domain}/pl/{m3u8_path}"
                try:
                    req = urllib.request.Request(url, headers={
                        "User-Agent": UA, "Referer": "https://cloudnestra.com/"
                    })
                    with urllib.request.urlopen(req, timeout=8) as r:
                        if r.status == 200: return (url, None)
                except: continue
        return None, None

    def _scrape_provider(name, movie_t, tv_t, tmdb_id, media_type, season, episode):
        return None, None

    def _selenium_via_cloudnestra(tmdb_id, media_type, season=1, episode=1, timeout=30):
        if media_type == "movie":
            vt_url = f"https://vidsrc.to/embed/movie/{tmdb_id}"
        else:
            vt_url = f"https://vidsrc.to/embed/tv/{tmdb_id}/{season}/{episode}"

        html1 = _get(vt_url, referer="https://vidsrc.to/")
        m = re.search(r'src="((?:https?:)?//vsembed\.ru/embed/[^"]+)"', html1 or "")
        if not m: return None
        vs_url = m.group(1)
        if vs_url.startswith('//'): vs_url = 'https:' + vs_url

        html2 = _get(vs_url, referer="https://vidsrc.to/")
        hashes = re.findall(r'data-hash="([^"]+)"', html2 or "")
        if not hashes: return None

        rcp_url = f"https://cloudnestra.com/rcp/{hashes[0]}"
        return _selenium_rcp(rcp_url, referer="https://vsembed.ru/", timeout=timeout)

    def _selenium_vidlink(tmdb_id, media_type, season=1, episode=1, timeout=30):
        driver_path = chromedriver_path()
        if not driver_path: return None, None
        
        url = f"https://vidlink.pro/movie/{tmdb_id}" if media_type == "movie" else f"https://vidlink.pro/tv/{tmdb_id}/{season}/{episode}"
        
        driver = None
        try:
            if _uc_ok():
                import undetected_chromedriver as uc
                opts = uc.ChromeOptions()
                opts.add_argument("--mute-audio")
                opts.add_argument("--no-sandbox")
                opts.add_argument("--disable-dev-shm-usage")
                opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})
                driver = uc.Chrome(options=opts, version_main=145, driver_executable_path=driver_path)
            else:
                return None, None

            driver.execute_cdp_cmd("Network.enable", {})
            driver.get(url)
            time.sleep(12)

            m3u8 = None
            vtt = None
            referer = "https://videostr.net/"
            origin = "https://videostr.net"

            for log in driver.get_log("performance"):
                try:
                    req_url = json.loads(log["message"])["message"]["params"]["request"]["url"]
                    if ".m3u8" in req_url and "proxy" in req_url and not m3u8:
                        m3u8 = req_url
                        # Try to parse embedded headers for re-use
                        import urllib.parse
                        qs = urllib.parse.parse_qs(urllib.parse.urlparse(req_url).query)
                        if "headers" in qs:
                            hdict = json.loads(qs["headers"][0])
                            referer = hdict.get("referer", referer)
                            origin = hdict.get("origin", origin)
                    elif ".vtt" in req_url and not vtt:
                        vtt = req_url
                except: pass
            
            driver.quit()

            # Resolve the proxy URL to an actual direct CDN URL using curl_cffi
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
                        # Find the actual final URL (after redirect)
                        final = resp.url
                        # If the content is an m3u8 playlist, the URL itself is the stream
                        m3u8 = str(final)
                        # If it's a multi-quality playlist, try to extract the best stream URL
                        content = resp.text
                        lines = content.strip().split('\n')
                        direct_streams = [l.strip() for l in lines if l.strip() and not l.startswith('#')]
                        if direct_streams:
                            # Resolve relative URLs against the m3u8 base
                            import urllib.parse as up
                            base = str(final)
                            resolved = up.urljoin(base, direct_streams[-1])
                            m3u8 = resolved
                except Exception:
                    pass  # Keep original proxy URL as fallback

            return m3u8, vtt
        except Exception:
            try: driver.quit()
            except: pass
            return None, None

    def _ytdlp(embed_url, quality="best", lang="fr", proxy=None):
        cmd = ["yt-dlp", "-g", "--no-warnings", embed_url]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip().split('\n')[0], None
        except: pass
        return None, None

    # Phase 0: Cloudnestra HTTP
    from .art import get_random_art
    spinner("Cloudnestra ...", art=get_random_art())
    url, vtt = _cloudnestra(tmdb_id, media_type, season, episode)
    if url:
        clear_line()
        success("Stream trouvé via cloudnestra")
        return url, vtt
    clear_line()

    # Phase 1: Scrapers HTTP
    for i, (name, movie_t, tv_t) in enumerate(providers, 1):
        spinner(f"[HTTP {i}/{len(providers)}] {name} ...", art=get_random_art())
        url, vtt = _scrape_provider(name, movie_t, tv_t, tmdb_id, media_type, season, episode)
        if url:
            clear_line()
            success(f"Stream trouvé via {name}")
            return url, vtt
    clear_line()

    # Phase 2: Selenium
    if chromedriver_path():
        warn("HTTP sans résultat — lancement Chromium headless ...")
        url, vtt = _selenium_via_cloudnestra(tmdb_id, media_type, season, episode)
        if url:
            clear_line()
            success("Stream intercepté via Chromium (Cloudnestra)")
            return url, vtt
        clear_line()

    # Phase 3: yt-dlp
    if ytdlp_ok():
        warn("Tentative yt-dlp ...")
        for name, movie_t, tv_t in providers[:3]:
            tpl = movie_t if media_type == "movie" else tv_t
            embed_url = tpl.format(id=tmdb_id, s=season, e=episode)
            url, vtt = _ytdlp(embed_url, quality=quality, lang=lang, proxy=proxy)
            if url:
                clear_line()
                success(f"Stream via yt-dlp ({name})")
                return url, vtt
        clear_line()

    # Phase 4: direct embed
    warn("Passage en mode mpv direct ...")
    name, movie_t, tv_t = providers[0]
    tpl = movie_t if media_type == "movie" else tv_t
    return tpl.format(id=tmdb_id, s=season, e=episode), None
