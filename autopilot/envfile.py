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


def update_env(updates: dict, path: str = "") -> None:
    """Tulis atau perbarui KEY=VALUE di file .env.

    - Jika key sudah ada, baris tersebut diperbarui.
    - Jika key belum ada, ditambahkan di akhir file.
    - Jika .env belum ada, dibuat dari .env.example (jika ada) lalu diperbarui.
    - Nilai di os.environ juga diperbarui agar langsung berlaku tanpa restart.
    """
    env_path = path or os.path.join(_ROOT, ".env")

    # Buat .env dari .env.example jika belum ada
    if not os.path.exists(env_path):
        example = os.path.join(_ROOT, ".env.example")
        if os.path.exists(example):
            import shutil
            shutil.copy(example, env_path)
        else:
            open(env_path, "w", encoding="utf-8").close()

    # Baca baris yang ada
    with open(env_path, encoding="utf-8") as f:
        lines = f.readlines()

    updated_keys = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, _, _ = stripped.partition("=")
            key = key.strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                updated_keys.add(key)
                continue
        new_lines.append(line)

    # Tambahkan key yang belum ada
    for key, val in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    # Update os.environ langsung agar berlaku tanpa restart
    for key, val in updates.items():
        if val:
            os.environ[key] = val
        elif key in os.environ:
            del os.environ[key]
