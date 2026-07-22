"""Sumber data kampanye & performa.

- Mode DEMO (default): generator performa realistis per kampanye — semua alur bisa
  diuji tanpa API sama sekali.
- Mode LIVE: menarik daftar kampanye + performa harian dari Shopee Ads API.
"""
import logging
import random
from datetime import date, timedelta

from . import db

log = logging.getLogger("autopilot.ads_source")

HARI_SEED = 30  # berapa hari performa historis yang di-generate di mode demo


# ------------------------------------------------------------------ DEMO generator
def _generate_perf_demo(c, kampanye, hari_ke_belakang: int = 1) -> None:
    """Generate performa 1 hari (kemarin) secara deterministik-tapi-hidup.
    Kampanye 'baik' menjaga ROAS 3-6; 'boros' 0.4-1.2 — agar rules mudah terpicu."""
    tgl = (date.today() - timedelta(days=hari_ke_belakang)).isoformat()
    rng = random.Random(f"{kampanye['id']}-{tgl}")  # stabil per kampanye per tanggal
    tipe = _kategori_demo(kampanye)
    budget = kampanye["daily_budget"] or 60000
    spend = budget * rng.uniform(0.55, 1.0)
    if tipe == "baik":
        roas = rng.uniform(3.0, 6.5)
    elif tipe == "sedang":
        roas = rng.uniform(1.5, 3.5)
    else:
        roas = rng.uniform(0.4, 1.3)
    gmv = spend * roas
    klik = int(spend / rng.uniform(600, 1400))
    impresi = int(klik / rng.uniform(0.008, 0.03)) or klik * 50
    konversi = max(0, gmv / rng.uniform(80000, 160000))
    db.put_perf(c, kampanye["id"], tgl, round(spend), round(gmv), impresi, klik, round(konversi, 1))


def _kategori_demo(kampanye) -> str:
    """Label performa demo dari nama kampanye (untuk skenario uji)."""
    n = (kampanye["nama"] or "").lower()
    if any(k in n for k in ("[baik]", "juara", "untung")):
        return "baik"
    if any(k in n for k in ("[boros]", "boncos", "rugi")):
        return "boros"
    return "sedang"


def backfill_demo(c, kampanye, n_hari: int = HARI_SEED) -> None:
    for i in range(n_hari, 0, -1):
        _generate_perf_demo(c, kampanye, hari_ke_belakang=i)


# ------------------------------------------------------------------ LIVE fetch
def _tarik_live(c, store_row) -> str:
    """Tarik kampanye + performa 7 hari dari API. Best-effort; field ditandai jika belum pasti."""
    from shopee_connector.client import ShopeeClient
    from shopee_connector.config import Config
    from shopee_connector.token_store import JsonFileTokenStore

    cfg = Config.from_env()
    ts = JsonFileTokenStore(cfg.token_dir)
    try:
        shop_id = int(store_row["shop_id_ext"])
    except (TypeError, ValueError):
        return f"shop_id tidak valid: {store_row['shop_id_ext']}"
    if ts.load(shop_id) is None:
        return "belum terotorisasi"
    client = ShopeeClient(cfg, ts)

    # 1) daftar kampanye produk (manual) — akronim halaman dok: get_product_level_campaign_id_list
    data = client.shop_call(shop_id, "/api/v2/ads/get_product_level_campaign_id_list",
                            ad_type="all", offset=0, limit=100)
    resp = data.get("response") or {}
    items = resp.get("campaign_list") or resp.get("campaign_id_list") or []
    n_k, n_p = 0, 0
    tgl_akhir = date.today() - timedelta(days=1)
    tgl_awal = tgl_akhir - timedelta(days=6)
    for it in items:
        cid_api = str(it.get("campaign_id") or it.get("campaignid") or "")
        if not cid_api:
            continue
        cid = db.upsert_campaign(c, store_row["id"], cid_api,
                                 it.get("campaign_name") or f"Campaign {cid_api}",
                                 type_="manual", bidding_method=it.get("bidding_method", "auto"),
                                 status=it.get("ad_status", "ongoing"),
                                 daily_budget=it.get("budget", 0) or 0,
                                 roas_target=it.get("roas_target", 0) or 0)
        n_k += 1
        # 2) performa harian per kampanye — field nama metrik: verifikasi dok
        perf = client.shop_call(
            shop_id, "/api/v2/ads/get_product_campaign_daily_performance",
            start_date=tgl_awal.strftime("%d-%m-%Y"), end_date=tgl_akhir.strftime("%d-%m-%Y"),
            campaign_id_list=cid_api)
        for row in (perf.get("response") or {}).get("result", []):
            # TODO-verifikasi nama field tanggal & metrik di respons dok Ads
            tgl = row.get("date") or row.get("stat_date") or ""
            if not tgl:
                continue
            db.put_perf(c, cid, tgl, row.get("expense", 0) or row.get("cost", 0),
                        row.get("broad_gmv", 0) or row.get("gmv", 0),
                        row.get("impression", 0), row.get("click", 0),
                        row.get("broad_order", 0) or row.get("conversion", 0))
            n_p += 1
    db.set_setting(c, f"sync_note_{store_row['id']}", f"API ok: {n_k} kampanye, {n_p} hari-performa")
    return f"{n_k} kampanye"


# ------------------------------------------------------------------ orkestrasi
def sinkron_semua(c) -> None:
    """Sinkron semua toko sesuai mode aktif."""
    mode_ = db.mode(c)
    for s in db.conn().execute("SELECT * FROM stores ORDER BY id").fetchall():
        try:
            if mode_ == "live":
                catatan = _tarik_live(c, s)
            else:
                # demo: kampanye dibuat oleh scripts/seed_demo; di sini cukup top-up
                # hari baru (kemarin) BILA belum ada — jangan timpa data yang sudah ada.
                kemarin = (date.today() - timedelta(days=1)).isoformat()
                for k in db.list_campaigns(c, store_id=s["id"]):
                    ada = c.execute("SELECT 1 FROM perf_daily WHERE campaign_id=? AND tanggal=?",
                                    (k["id"], kemarin)).fetchone()
                    if not ada:
                        _generate_perf_demo(c, k, hari_ke_belakang=1)
                catatan = "demo"
            db.conn().execute("UPDATE stores SET last_sync_at=datetime('now','localtime') WHERE id=?",
                              (s["id"],))
            db.set_setting(c, f"sync_note_{s['id']}", catatan)
        except Exception as e:  # noqa: BLE001
            log.exception("sinkron toko %s gagal", s["nama"])
            db.set_setting(c, f"sync_note_{s['id']}", f"ERROR: {e}")
    c.commit()
