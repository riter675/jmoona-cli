#!/usr/bin/env bash
# jmoona-cli — Installateur Linux / macOS
# Usage: curl -fsSL https://raw.githubusercontent.com/.../install.sh | bash

set -e

BOLD="\033[1m"; GREEN="\033[32m"; YELLOW="\033[33m"; RED="\033[31m"; RESET="\033[0m"
info()  { echo -e "${BOLD}${GREEN}[jmoona]${RESET} $*"; }
warn()  { echo -e "${BOLD}${YELLOW}[jmoona]${RESET} $*"; }
error() { echo -e "${BOLD}${RED}[jmoona]${RESET} $*"; exit 1; }

OS="$(uname -s)"
info "Détection du système : $OS"

# ── 1. Python 3.10+ ──────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    case "$OS" in
        Linux)
            if command -v apt-get &>/dev/null; then
                sudo apt-get update -q && sudo apt-get install -y python3 python3-pip
            elif command -v dnf &>/dev/null; then
                sudo dnf install -y python3 python3-pip
            elif command -v pacman &>/dev/null; then
                sudo pacman -Sy --noconfirm python python-pip
            else
                error "Installez Python 3.10+ manuellement depuis https://python.org"
            fi
            ;;
        Darwin)
            if command -v brew &>/dev/null; then
                brew install python
            else
                error "Installez Homebrew (https://brew.sh) puis relancez ce script."
            fi
            ;;
    esac
fi

PY_VER=$(python3 -c "import sys; print(sys.version_info[:2])")
info "Python détecté : $PY_VER"

# ── 2. mpv ────────────────────────────────────────────────────────────────────
if ! command -v mpv &>/dev/null; then
    warn "mpv non trouvé — installation..."
    case "$OS" in
        Linux)
            if command -v apt-get &>/dev/null; then
                sudo apt-get install -y mpv
            elif command -v dnf &>/dev/null; then
                sudo dnf install -y mpv
            elif command -v pacman &>/dev/null; then
                sudo pacman -Sy --noconfirm mpv
            fi
            ;;
        Darwin)
            brew install mpv
            ;;
    esac
else
    info "mpv : OK"
fi

# ── 3. yt-dlp ─────────────────────────────────────────────────────────────────
if ! command -v yt-dlp &>/dev/null; then
    warn "yt-dlp non trouvé — installation..."
    pip3 install --user yt-dlp 2>/dev/null || sudo pip3 install yt-dlp
else
    info "yt-dlp : OK"
fi

# ── 4. fzf (optionnel) ────────────────────────────────────────────────────────
if ! command -v fzf &>/dev/null; then
    warn "fzf non trouvé (optionnel, meilleurs menus) — installation..."
    case "$OS" in
        Linux)
            if command -v apt-get &>/dev/null; then sudo apt-get install -y fzf; fi
            ;;
        Darwin)
            brew install fzf
            ;;
    esac
else
    info "fzf : OK"
fi

# ── 5. Chromium + chromedriver (optionnel, accélère certains streams) ─────────
if ! command -v chromium-browser &>/dev/null && ! command -v chromium &>/dev/null && ! command -v google-chrome &>/dev/null; then
    warn "Chromium non trouvé (optionnel). Pour l'installer:"
    case "$OS" in
        Linux)  warn "  sudo apt install chromium-browser  # Debian/Ubuntu" ;;
        Darwin) warn "  brew install --cask chromium" ;;
    esac
fi

# ── 6. Dépendances Python pour display headless (Linux uniquement) ─────────────
if [ "$OS" = "Linux" ]; then
    if ! python3 -c "import Xvfb" &>/dev/null 2>&1; then
        sudo apt-get install -y xvfb 2>/dev/null || true
    fi
fi

# ── 7. Installer jmoona-cli ───────────────────────────────────────────────────
info "Installation de jmoona-cli..."

# Cloner ou mettre à jour
if [ -d "$HOME/.local/share/jmoona-cli" ]; then
    info "Mise à jour de jmoona-cli..."
    git -C "$HOME/.local/share/jmoona-cli" pull --ff-only
else
    git clone --depth=1 https://github.com/riter675/jmoona-cli.git "$HOME/.local/share/jmoona-cli"
fi

# Installer le package Python
pip3 install --user --quiet "$HOME/.local/share/jmoona-cli"

# ── 8. Ajouter ~/.local/bin au PATH si besoin ─────────────────────────────────
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    warn "Ajout de ~/.local/bin au PATH dans votre shell..."
    SHELL_RC="$HOME/.bashrc"
    [[ "$SHELL" == *"zsh"* ]] && SHELL_RC="$HOME/.zshrc"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
    warn "Rechargez votre shell : source $SHELL_RC"
fi

info "✅ Installation terminée ! Lancez : jmoona"
