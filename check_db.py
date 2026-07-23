import sqlite3, os, sys

db = "autopilot.db"
if not os.path.exists(db):
    print("DB belum ada — jalankan run.py dulu")
    sys.exit(0)

con = sqlite3.connect(db)
con.row_factory = sqlite3.Row

toko = con.execute("SELECT id, shop_id_ext, nama, last_sync_at FROM stores ORDER BY id").fetchall()
print(f"Jumlah toko di DB: {len(toko)}")
for t in toko:
    print(f"  id={t['id']} shop_id={t['shop_id_ext']} nama={t['nama']} sync={t['last_sync_at']}")

mode_row = con.execute("SELECT value FROM settings WHERE key='mode'").fetchone()
print(f"Mode: {mode_row['value'] if mode_row else 'demo'}")

tokens_dir = "tokens"
if os.path.isdir(tokens_dir):
    files = [f for f in os.listdir(tokens_dir) if f.endswith(".json")]
    print(f"File token tersimpan: {files or 'tidak ada'}")
else:
    print("Folder ./tokens belum ada")

env_file = ".env"
if os.path.exists(env_file):
    with open(env_file, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#") and "=" in l]
    pid = next((l for l in lines if l.startswith("SHOPEE_PARTNER_ID")), "SHOPEE_PARTNER_ID=(kosong)")
    rurl = next((l for l in lines if l.startswith("SHOPEE_REDIRECT_URL")), "SHOPEE_REDIRECT_URL=(kosong)")
    print(f".env: {pid}")
    print(f".env: {rurl}")
else:
    print(".env belum ada")
