#!/usr/bin/env python3
"""Entry point Shopee Ads Autopilot.

    python run.py                    # server web + scheduler otomatis (untuk PC 24 jam)
    python run.py --no-scheduler     # hanya server web (evaluasi manual / via Task Scheduler)
    python run.py --port 9000        # ganti port (default 8765)

Buka dashboard di:  http://127.0.0.1:8765
"""
import argparse
import logging
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from autopilot import db, engine          # noqa: E402
from autopilot.envfile import load_env    # noqa: E402

log = logging.getLogger("autopilot.run")


def _scheduler_loop(stop: threading.Event) -> None:
    """Jalankan satu siklus evaluasi tiap `interval_menit` (dibaca ulang tiap putaran)."""
    while not stop.is_set():
        try:
            c = db.conn()
            if db.is_kill(c):
                log.info("Kill-switch aktif — siklus otomatis dilewati.")
            else:
                ringkas = engine.jalankan_satu_siklus(c)
                log.info("Siklus otomatis: %s", ringkas)
        except Exception:  # noqa: BLE001 — scheduler tidak boleh mati
            log.exception("Siklus otomatis gagal (dicoba lagi pada interval berikutnya)")
        # tidur dalam potongan 5 dtk agar shutdown responsif & interval bisa berubah
        menit = max(5, db.jendela(db.conn()))
        stop.wait(timeout=menit * 60)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8765")))
    p.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    p.add_argument("--no-scheduler", action="store_true",
                   help="matikan scheduler otomatis (evaluasi manual dari dashboard / Task Scheduler)")
    args = p.parse_args()

    load_env(verbose=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    db.init(os.environ.get("AUTOPILOT_DB",
                           os.path.join(os.path.dirname(os.path.abspath(__file__)), "autopilot.db")))

    if not args.no_scheduler:
        t = threading.Thread(target=_scheduler_loop, args=(threading.Event(),),
                             name="autopilot-scheduler", daemon=True)
        t.start()
        log.info("Scheduler aktif — interval awal %s menit (ubah di Settings)",
                 db.jendela(db.conn()))
    else:
        log.info("Scheduler nonaktif (--no-scheduler)")

    print("=" * 64)
    print("  🚀 Shopee Ads Autopilot")
    print(f"  Dashboard : http://{args.host}:{args.port}")
    print(f"  Mode awal : {db.mode(db.conn()).upper()}  (kill-switch di pojok kanan atas)")
    print("=" * 64)

    import uvicorn
    uvicorn.run("autopilot.web:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
