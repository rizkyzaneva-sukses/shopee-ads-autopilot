#!/usr/bin/env python3
"""Jalankan SATU siklus evaluasi engine lalu keluar.

Dipakai untuk:
- pengujian manual:  python scripts/run_engine_once.py
- Windows Task Scheduler (alternatif bila server web tidak nyala 24 jam):

    schtasks /create /tn "ShopeeAdsAutopilot" ^
      /tr "\"C:\\path\\ke\\python.exe\" \"C:\\path\\ke\\shopee-ads-autopilot\\scripts\\run_engine_once.py\"" ^
      /sc minute /mo 60

  (sesuaikan path python & folder aplikasi Anda)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # path relatif (.env, db) stabil

from autopilot import db, engine            # noqa: E402
from autopilot.envfile import load_env      # noqa: E402


def main() -> None:
    load_env()
    c = db.init(os.environ.get("AUTOPILOT_DB", "autopilot.db"))
    if db.is_kill(c):
        print("⛔ Kill-switch aktif — siklus dilewati (nonaktifkan dari dashboard).")
        return
    ringkas = engine.jalankan_satu_siklus(c)
    print(f"✅ Siklus selesai: {ringkas} | mode={db.mode(c)}")


if __name__ == "__main__":
    main()
