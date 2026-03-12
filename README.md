# 🎬 jmoona-cli

```
      _                                        _ _ 
     (_)                                      | (_)
      _ _ __ ___   ___   ___  _ __   __ _  ___| |_ 
     | | '_ ` _ \ / _ \ / _ \| '_ \ / _` |/ __| | |
     | | | | | | | (_) | (_) | | | | (_| | (__| | |
     | |_| |_| |_|\___/ \___/|_| |_|\__,_|\___|_|_|
```

> **L'émulateur ultime de films et séries** — streaming depuis votre terminal

---

## ✨ Fonctionnalités

- 🔍 Recherche de films & séries via TMDB
- 🎬 Streaming en un clic via `mpv`
- 🔤 Sous-titres français automatiques (OpenSubtitles)
- 📥 Téléchargement avec `yt-dlp`
- 🕹️ Reprise de lecture automatique
- 💾 Historique de visionnage
- 🌐 Multi-sources (Cloudnestra, vidsrc, smashystream, ...)
- 🖥️ Compatible Linux · macOS · Windows · Docker

---

## 📦 Installation rapide

### 🐧 Linux / 🍎 macOS

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/riter675/jmoona-cli/main/install.sh)
```

### 🪟 Windows (PowerShell en administrateur)

```powershell
irm https://raw.githubusercontent.com/riter675/jmoona-cli/main/install.ps1 | iex
```

### 🐳 Docker (n'importe quel OS)

```bash
docker build -t jmoona .
# Avec affichage vidéo sur l'écran hôte (Linux) :
docker run -it --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v "$HOME/Downloads/jmoona:/root/Downloads/jmoona" \
  jmoona
```

### Installation manuelle (pip)

```bash
git clone https://github.com/riter675/jmoona-cli.git
cd jmoona-cli
pip install -e .
jmoona
```

---

## ⚠️ Prérequis

| Outil | Rôle | Requis |
|-------|------|--------|
| Python 3.10+ | Moteur | ✅ Obligatoire |
| `mpv` | Lecteur vidéo | ✅ Obligatoire |
| `yt-dlp` | Extracteur de streams | ✅ Obligatoire |
| `fzf` | Interface menus améliorée | ⚡ Recommandé |
| `ffmpeg` / `ffprobe` | Analyse des pistes | ⚡ Recommandé |
| Chromium + chromedriver | Extraction Selenium | 🔧 Optionnel |

### Installation des prérequis

**Ubuntu/Debian:**
```bash
sudo apt install mpv yt-dlp fzf ffmpeg python3 python3-pip
pip install jmoona-cli
```

**Fedora:**
```bash
sudo dnf install mpv yt-dlp fzf ffmpeg python3 python3-pip
```

**Arch Linux:**
```bash
sudo pacman -S mpv yt-dlp fzf ffmpeg python python-pip
```

**macOS (Homebrew):**
```bash
brew install mpv yt-dlp fzf ffmpeg python
pip3 install jmoona-cli
```

**Windows (winget + pip):**
```powershell
winget install mpv.mpv yt-dlp.yt-dlp Git.Git Python.Python.3.12
pip install jmoona-cli
```

---

## 🚀 Utilisation

```bash
jmoona              # Lancer l'interface interactive
jmoona "Inception"  # Recherche directe
```

### Navigation
- `↑↓` ou numéro — choisir dans les menus
- `Enter` — valider
- `q` ou `Ctrl+C` — quitter
- Dans mpv : `f` = plein écran, `←→` = avance/recul, `q` = quitter

### Modes de lecture

| Mode | Description |
|------|-------------|
| 🎵 **Auto** | FR si disponible, anglais sinon (recommandé) |
| 🔤 **VOSTFR** | Audio original + sous-titres français (idéal animés) |
| 🇬🇧 **VA** | Version originale sans sous-titres |

---

## ⚙️ Configuration

Fichier de config par OS :
- **Linux** : `~/.config/jmoona/config.json`
- **macOS** : `~/Library/Application Support/jmoona/config.json`
- **Windows** : `%APPDATA%\jmoona\config.json`

Options disponibles :

```json
{
  "player": "mpv",
  "player_args": "--fs",
  "quality": "best",
  "provider": "auto",
  "use_fzf": true,
  "resume": true,
  "download_dir": "~/Downloads/jmoona"
}
```

---

## 🔧 Dépendances Python

```
requests>=2.28.0
selenium>=4.9.0
undetected-chromedriver>=3.5.0
pyvirtualdisplay>=3.0    # Linux uniquement
curl-cffi>=0.6.0
```

---

## 📁 Structure du projet

```
jmoona-cli/
├── jmoona/
│   ├── app.py          # Logique principale
│   ├── cli.py          # Point d'entrée CLI
│   ├── extractor.py    # Extraction des streams
│   ├── player.py       # Lecture via mpv
│   ├── downloader.py   # Téléchargement via yt-dlp
│   ├── subtitles.py    # Sous-titres via OpenSubtitles
│   ├── tmdb.py         # API TMDB
│   ├── ui.py           # Interface terminal
│   ├── art.py          # ASCII art
│   ├── language.py     # Détection pistes audio
│   ├── storage.py      # Historique & reprise
│   ├── config.py       # Configuration cross-platform
│   └── providers.py    # Liste des providers
├── pyproject.toml
├── install.sh          # Installateur Linux/macOS
├── install.ps1         # Installateur Windows
├── Dockerfile
└── README.md
```

---

## 🐛 Problèmes courants

**`mpv: command not found`** → Installez mpv (voir prérequis ci-dessus)

**Stream introuvable** → Essayez un autre provider : `jmoona` → paramètres → providers

**Chromium manquant** → Normal, Selenium est optionnel. Les streams HTTP fonctionnent sans.

**Windows : couleurs absentes** → Activez les couleurs ANSI : `Set-ItemProperty HKCU:\Console VirtualTerminalLevel 1`

---

## 📄 Licence

MIT — fait avec ❤️ par jmoona
