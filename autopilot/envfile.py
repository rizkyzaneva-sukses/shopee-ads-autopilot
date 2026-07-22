"""Loader .env minimal (tanpa dependency) — dipakai run.py & scripts di Windows.

Format yang didukung:
    KEY=VALUE            # komentar diakhir boleh
    # baris komentar
Value boleh dikutip ("..." atau '...'). Variabel yang sudah ada di environment
TIDAK ditimpa (environment asli menang).
"""
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env(path: str = "", verbose: bool = False) -> int:
    path = path or os.path.join(_ROOT, ".env")
    if not os.path.exists(path):
        return 0
    n = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if " #" in val:  # komentar inline sederhana
                val = val.split(" #", 1)[0].rstrip()
            if key and key not in os.environ:
                os.environ[key] = val
                n += 1
    if verbose:
        print(f"[envfile] {n} variabel dimuat dari {path}")
    return n
