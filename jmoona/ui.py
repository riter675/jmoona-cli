import sys
import re

class C:
    RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
    RED = "\033[91m";  GREEN = "\033[92m"; YELLOW = "\033[93m"
    BLUE = "\033[94m"; MAGENTA = "\033[95m"; CYAN = "\033[96m"
    WHITE = "\033[97m"; GRAY = "\033[90m"

def _strip_ansi(s):
    return re.sub(r'\033\[[0-9;]*m', '', s)

_last_art_lines = 0

def spinner(text, art=None):
    global _last_art_lines
    if art:
        print(art)
        _last_art_lines = len(art.strip('\n').split('\n')) + 1
    sys.stdout.write(f"\r{C.DIM}{text}{C.RESET}")
    sys.stdout.flush()

def clear_line():
    global _last_art_lines
    if _last_art_lines > 0:
        # Move cursor up by _last_art_lines and clear everything below
        sys.stdout.write(f"\033[{_last_art_lines}A\033[J")
        _last_art_lines = 0
    else:
        sys.stdout.write("\r\033[K")
    sys.stdout.flush()

def success(text):
    print(f"{C.GREEN}✓{C.RESET} {text}")

def warn(text):
    print(f"{C.YELLOW}⚠{C.RESET} {text}")

def error(text):
    print(f"{C.RED}✗{C.RESET} {text}")
    
def fzf_available():
    import shutil
    return shutil.which("fzf") is not None

def fzf_select(items, prompt="Choisir"):
    import subprocess
    input_str = "\n".join(items)
    try:
        proc = subprocess.Popen(
            ["fzf", "--prompt", f"{prompt} > ", "--ansi"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True
        )
        stdout, _ = proc.communicate(input=input_str)
        if proc.returncode == 0 and stdout:
            return stdout.strip().split("\n")
        elif proc.returncode in (1, 130): # user cancelled
            return None
    except Exception:
        pass
    # fzf failed (e.g. exit 2) or threw an exception -> fallback to numbered
    return False

def fzf_or_numbered(items, prompt="Choisir", key_fn=None, use_fzf=True):
    labels = [key_fn(i) if key_fn else str(i) for i in items]
    labels_plain = [_strip_ansi(l) for l in labels]

    if use_fzf and fzf_available():
        chosen = fzf_select(labels, prompt=prompt)
        if chosen is None:
            return None # user cancelled
        if chosen is not False:
            chosen_plain = _strip_ansi(chosen[0])
            for item, lp in zip(items, labels_plain):
                if lp == chosen_plain: return item
            for item, lp in zip(items, labels_plain):
                if chosen_plain in lp or lp in chosen_plain: return item
            return None
        # If chosen is False, fzf errored out. Fall through to numbered menu.

    print(f"\n{'─'*60}")
    for n, label in enumerate(labels, 1):
        print(f"  {n}.  {label}")
    print('─'*60)
    while True:
        try:
            raw = input(f"\n{prompt} (1-{len(items)}, q=quitter): ").strip()
            if raw.lower() in ("q", "quit", "exit"): return None
            idx = int(raw) - 1
            if 0 <= idx < len(items): return items[idx]
        except (ValueError, EOFError, KeyboardInterrupt): return None
