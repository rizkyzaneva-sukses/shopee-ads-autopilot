#!/usr/bin/env python3
"""Isi database dengan DATA DEMO: 6 toko cabang + kampanye semua tipe + performa 30 hari.

    python scripts/seed_demo.py
    python scripts/seed_demo.py --reset     # hapus DB dulu (hati-hati)

Skenario yang disiapkan (dari nama kampanye — dipakai generator demo):
    [baik]/juara  -> ROAS 3.0–6.5  (cocok untuk aturan naikkan budget)
    [boros]/boncos -> ROAS 0.4–1.3 (cocok untuk aturan rem/pause)
    lainnya        -> ROAS 1.5–3.5
"""
import argparse
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autopilot import db, ads_source          # noqa: E402
from autopilot.envfile import load_env        # noqa: E402

DB_PATH = os.environ.get("AUTOPILOT_DB",
                         os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                      "autopilot.db"))

TOKO = [
    ("demo-1101", "Cabang Bandung (Pusat)", 400_000),
    ("demo-1102", "Cabang Jakarta",         350_000),
    ("demo-1103", "Cabang Surabaya",        300_000),
    ("demo-1104", "Cabang Medan",           250_000),
    ("demo-1105", "Cabang Semarang",        200_000),
    ("demo-1106", "Cabang Makassar",        200_000),
]

# (suffix ext_id, nama, tipe, bidding, status, budget, roas_target)
KAMPANYE = [
    ("m1", "[baik] Search - Hoodie Oversize",       "manual", "auto",   "ongoing", 80_000, 4.0),
    ("m2", "[boros] Search - Celana Cargo Boncos",  "manual", "manual", "ongoing", 60_000, 0),
    ("g1", "[baik] GMV Max - Produk Juara",         "gms",    "auto",   "ongoing", 100_000, 5.0),
    ("a1", "Iklan Produk Otomatis - Katalog",       "auto",   "auto",   "ongoing", 50_000, 0),
    ("m3", "Search - Kaos Polos Reguler",           "manual", "auto",   "paused",  40_000, 3.0),
]

ATURAN = [
    dict(nama="Rem kampanye boncos (ROAS < 1)", enabled=1, priority=10,
         scope_type="all", scope_value="", metric="roas", window_days=7,
         comparator="lt", threshold=1.0, cond2_metric="spend", cond2_comparator="gte",
         cond2_threshold=100_000, cond2_window=7, action="budget_down", action_value=30,
         budget_floor=20_000, budget_ceiling=0, max_actions_day=1, requires_confirm=0,
         notify="telegram"),
    dict(nama="Gas kampanye juara (ROAS ≥ 3)", enabled=1, priority=20,
         scope_type="type", scope_value="manual", metric="roas", window_days=7,
         comparator="gte", threshold=3.0, cond2_metric="", cond2_comparator="gte",
         cond2_threshold=0, cond2_window=7, action="budget_up", action_value=20,
         budget_floor=20_000, budget_ceiling=500_000, max_actions_day=1, requires_confirm=0,
         notify="telegram"),
    dict(nama="Pause total boncos (ROAS < 0.5, 14 hari)", enabled=1, priority=5,
         scope_type="all", scope_value="", metric="roas", window_days=14,
         comparator="lt", threshold=0.5, cond2_metric="", cond2_comparator="gte",
         cond2_threshold=0, cond2_window=7, action="pause", action_value=0,
         budget_floor=20_000, budget_ceiling=0, max_actions_day=1, requires_confirm=1,
         notify="telegram"),
    dict(nama="Pengingat migrasi iklan otomatis", enabled=1, priority=90,
         scope_type="type", scope_value="auto", metric="spend", window_days=7,
         comparator="gt", threshold=50_000, cond2_metric="", cond2_comparator="gte",
         cond2_threshold=0, cond2_window=7, action="notify", action_value=0,
         budget_floor=20_000, budget_ceiling=0, max_actions_day=1, requires_confirm=0,
         notify="telegram"),
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reset", action="store_true", help="hapus database lama sebelum seeding")
    args = ap.parse_args()
    load_env()

    if args.reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"🗑  Database lama dihapus: {DB_PATH}")

    c = db.init(DB_PATH)
    db.set_setting(c, "mode", "demo")      # pastikan mulai dari mode aman
    db.set_setting(c, "kill", "0")
    db.set_setting(c, "interval_menit", "60")

    # --- toko & kampanye + backfill performa ---
    n_k = 0
    for shop_ext, nama, plafon in TOKO:
        sid = db.upsert_store(c, shop_ext, nama)
        c.execute("UPDATE stores SET plafon_harian=?, autopilot_on=1 WHERE id=?", (plafon, sid))
        for suf, knama, tipe, bidding, status, budget, roas_target in KAMPANYE:
            cid = db.upsert_campaign(c, sid, f"{shop_ext}-{suf}", knama, type_=tipe,
                                     bidding_method=bidding, status=status,
                                     daily_budget=budget, roas_target=roas_target)
            row = db.get_campaign(c, cid)
            ads_source.backfill_demo(c, row, ads_source.HARI_SEED)
            n_k += 1
    print(f"✅ {len(TOKO)} toko, {n_k} kampanye, performa {ads_source.HARI_SEED} hari ke belakang dibuat.")

    # --- aturan contoh (dry-run 24 jam, sama seperti buatan form) ---
    dryrun = (datetime.now() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    n_r = 0
    for a in ATURAN:
        sudah = c.execute("SELECT id FROM rules WHERE nama=?", (a["nama"],)).fetchone()
        if sudah:
            continue
        a = dict(a, dryrun_until=dryrun)
        db.simpan_rule(c, a)
        n_r += 1
    c.commit()
    print(f"✅ {n_r} aturan contoh ditambahkan (otomatis dry-run 24 jam pertama).")

    # --- satu siklus evaluasi agar dashboard langsung hidup ---
    from autopilot import engine
    ringkas = engine.jalankan_satu_siklus(c)
    print(f"▶ Siklus evaluasi pertama: {ringkas}")
    print(f"\nSelesai. Database: {DB_PATH}")
    print("Jalankan server:  python run.py   →   buka http://127.0.0.1:8765")


if __name__ == "__main__":
    main()
