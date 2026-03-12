# jmoona-cli — Installateur Windows (PowerShell)
# Usage: iwr -useb https://raw.githubusercontent.com/.../install.ps1 | iex

$ErrorActionPreference = "Stop"

function info($msg)  { Write-Host "[jmoona] $msg" -ForegroundColor Green }
function warn($msg)  { Write-Host "[jmoona] $msg" -ForegroundColor Yellow }
function fail($msg)  { Write-Host "[jmoona] ERREUR: $msg" -ForegroundColor Red; exit 1 }

info "=== Installateur jmoona-cli pour Windows ==="

# ── 1. Vérifier Python 3.10+ ──────────────────────────────────────────────────
try {
    $pyver = python --version 2>&1
    info "Python détecté : $pyver"
} catch {
    warn "Python non trouvé. Téléchargement et installation..."
    $pyInstaller = "$env:TEMP\python_installer.exe"
    Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe" -OutFile $pyInstaller
    Start-Process -FilePath $pyInstaller -Args "/quiet InstallAllUsers=1 PrependPath=1" -Wait
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine")
    info "Python installé."
}

# ── 2. Vérifier winget (Windows Package Manager) ──────────────────────────────
$hasWinget = Get-Command winget -ErrorAction SilentlyContinue

# ── 3. mpv ────────────────────────────────────────────────────────────────────
$mpvOk = $false
try { mpv --version | Out-Null; $mpvOk = $true; info "mpv : OK" } catch {}
if (-not $mpvOk) {
    warn "mpv non trouvé — installation via winget (shinchiro build)..."
    if ($hasWinget) {
        winget install -e --id shinchiro.mpv --silent 2>$null
        # Refresh PATH so mpv.exe is found immediately in this session
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("PATH","User")
        # mpv installs to "MPV Player" — add it if not already on PATH
        $mpvDir = "C:\Program Files\MPV Player"
        if ((Test-Path $mpvDir) -and ($env:PATH -notlike "*MPV Player*")) {
            [System.Environment]::SetEnvironmentVariable("PATH", $env:PATH + ";$mpvDir", "User")
            $env:PATH += ";$mpvDir"
            info "mpv ajouté au PATH : $mpvDir"
        }
        try { mpv --version | Out-Null; info "mpv : OK" } catch { warn "mpv installé mais redémarrez le terminal pour l'utiliser." }
    } else {
        warn "winget non disponible. Installez mpv manuellement : https://mpv.io/installation/"
    }
}

# ── 4. yt-dlp ─────────────────────────────────────────────────────────────────
$ytdlpOk = $false
try { yt-dlp --version | Out-Null; $ytdlpOk = $true; info "yt-dlp : OK" } catch {}
if (-not $ytdlpOk) {
    try { python -m yt_dlp --version | Out-Null; $ytdlpOk = $true; info "yt-dlp : OK (python -m)" } catch {}
}
if (-not $ytdlpOk) {
    warn "yt-dlp non trouvé — installation..."
    python -m pip install yt-dlp
    # Refresh PATH
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH","User")
    info "yt-dlp installé."
}

# ── 5. Git ────────────────────────────────────────────────────────────────────
try {
    git --version | Out-Null
    info "git : OK"
} catch {
    warn "git non trouvé — installation via winget..."
    if ($hasWinget) {
        winget install -e --id Git.Git --silent
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine")
    } else {
        warn "Installez Git manuellement : https://git-scm.com"
    }
}

# ── 6. Chromedriver (optionnel) ───────────────────────────────────────────────
$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
if (-not (Test-Path $chromePath)) {
    warn "Chrome non trouvé (optionnel). Pour l'installer:"
    warn "  winget install -e --id Google.Chrome"
}

# ── 7. Installer jmoona-cli ───────────────────────────────────────────────────
$installDir = "$env:LOCALAPPDATA\jmoona-cli"
info "Installation de jmoona-cli dans $installDir ..."

if (Test-Path $installDir) {
    info "Mise à jour..."
    git -C $installDir pull --ff-only
} else {
    git clone --depth=1 https://github.com/riter675/jmoona-cli.git $installDir
}

pip install -e $installDir --quiet

info ""
info "✅ Installation terminée !"
info "Lancez une nouvelle invite de commandes et tapez :  jmoona"
