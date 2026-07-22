#!/usr/bin/env python3
"""Otorisasi toko Shopee (OAuth resmi) → token tersimpan + toko terdaftar di Autopilot.

Pakai:
  python scripts/authorize_shop.py --nama "Cabang Bandung"                 # langkah 1: cetak URL
  python scripts/authorize_shop.py --nama "Cabang Bandung" --pasted-url "URL_REDIRECT_HASIL"
  python scripts/authorize_shop.py --nama "Cabang Bandung" --code KODE --shop-id 123456

Ulangi untuk SETIAP toko/cabang. Token berlaku ±4 jam dan di-refresh otomatis oleh client.
"""
import argparse
import os
import sys
import time
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autopilot import db                                   # noqa: E402
from autopilot.envfile import load_env                    # noqa: E402
from shopee_connector import auth                         # noqa: E402
from shopee_connector.client import ShopeeClient          # noqa: E402
from shopee_connector.config import Config                # noqa: E402
from shopee_connector.token_store import JsonFileTokenStore  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--nama", default="", help="nama toko untuk ditampilkan di dashboard")
    p.add_argument("--code")
    p.add_argument("--shop-id", type=int)
    p.add_argument("--pasted-url", help="URL redirect lengkap hasil otorisasi")
    args = p.parse_args()

    load_env()
    cfg = Config.from_env()
    store = JsonFileTokenStore(cfg.token_dir)
    client = ShopeeClient(cfg, store)

    if args.pasted_url:
        qs = parse_qs(urlparse(args.pasted_url).query)
        args.code = (qs.get("code") or [args.code])[0]
        args.shop_id = int((qs.get("shop_id") or [args.shop_id or 0])[0])

    if not args.code or not args.shop_id:
        print("Langkah otorisasi toko:")
        print(f"1. Pastikan redirect URL terdaftar di App Console: {cfg.redirect_url or '(belum di-set!)'}")
        print("2. Buka URL ini di browser, login sebagai PEMILIK TOKO, klik Setujui:\n")
        print("   " + auth.build_authorization_url(cfg) + "\n")
        print("3. Salin URL hasil redirect, lalu jalankan:")
        nama = f' --nama "{args.nama}"' if args.nama else ""
        print(f'   python scripts/authorize_shop.py{nama} --pasted-url "URL_HASIL_REDIRECT"')
        return

    token = auth.get_access_token(client, args.code, shop_id=args.shop_id)
    store.save(args.shop_id, token)

    # daftarkan / perbarui nama toko di dashboard Autopilot
    conn = db.init(os.environ.get("AUTOPILOT_DB", "autopilot.db"))
    db.upsert_store(conn, str(args.shop_id), args.nama or f"Toko {args.shop_id}")
    conn.commit()

    print(f"✅ SUKSES. Toko '{args.nama or args.shop_id}' (shop_id {args.shop_id}) terhubung.")
    print(f"   Token tersimpan di {cfg.token_dir}, berlaku ± s/d "
          f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(token.expires_at))} (refresh otomatis).")
    print("   Tarik kampanye pertama kali: klik '↻ Sinkron + Evaluasi' di dashboard (mode LIVE).")


if __name__ == "__main__":
    main()
