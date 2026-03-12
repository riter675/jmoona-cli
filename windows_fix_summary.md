# Windows Compatibility Fixes

## 1. yt-dlp Detection (OS-Agnostic with Windows Fallback)
On Windows, `pip install yt-dlp` often places the executable in a `Scripts/` folder that isn't in the global `PATH`. 
- **Change**: `ytdlp_ok()` now checks both `shutil.which("yt-dlp")` and runs `python -m yt_dlp --version`.
- **Why**: This ensures that even if the `.exe` isn't globally recognized, the tool can still work via the Python module interface.

## 2. mpv Installation (Windows Specific)
The `install.ps1` script had an incorrect package ID and lacked environment setup.
- **Change**: Updated package ID to `shinchiro.mpv`.
- **Change**: Added logic to automatically detect the installation directory (`C:\Program Files\MPV Player`) and add it to the USER's `PATH` via `[System.Environment]::SetEnvironmentVariable`.

## 3. Extraction Fallback Logic
Previously, if all extraction phases failed, the code passed a raw HTML embed URL to `mpv`.
- **Change**: Replaced the silent failure with a global `yt-dlp` sweep across all providers.
- **Change**: Added clear error messages if no stream is found, preventing `mpv` from launching and immediately closing.

## 4. Path Handling
Verified that `config.py` uses `sys.platform` to determine `CONFIG_DIR`:
- **Windows**: `%APPDATA%\jmoona`
- **macOS**: `~/Library/Application Support/jmoona`
- **Linux**: `~/.config/jmoona`
