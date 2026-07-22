"""Eksekutor aksi.

- simulasi(): mode demo/dry-run — hanya mengubah DB lokal agar alur terlihat nyata.
- live()    : memanggil Shopee Ads API via shopee_connector.

CATATAN VERIFIKASI (tingkat-2, per konvensi proyek ini):
nama field body untuk `edit_manual_product_ads` / GMS / status pause-resume
DITANDAI — cocokkan dengan halaman dokumentasi modul Ads saat akun developer aktif.
Endpoint tulis ikut deprecated plan? create/edit_auto_product_ads ditandai
'coming offline soon' oleh Shopee — executor menolak menulis ke kampanye type='auto'.
"""
import logging
from typing import Tuple

log = logging.getLogger("autopilot.executor")


# ------------------------------------------------------------------ preview (dry-run)
def preview(k, rule, aksi: str, nilai_aksi: str) -> str:
    """Label 'akan terjadi apa' untuk dry-run — TIDAK menulis apa pun."""
    if aksi == "set_budget":
        return f"Budget Rp {k['daily_budget'] or 0:,.0f} → Rp {float(nilai_aksi or 0):,.0f}".replace(",", ".")
    if aksi == "set_status":
        return f"Status → {nilai_aksi}"
    if aksi.startswith("bid_"):
        return f"Bid keyword disesuaikan {rule['action_value']}%"
    if aksi == "notify":
        return "Notifikasi analisa"
    return f"Aksi {aksi}"


# ------------------------------------------------------------------ simulasi
def simulasi(c, k, rule, aksi: str, nilai_aksi: str) -> Tuple[str, str]:
    if aksi == "set_budget":
        baru = float(nilai_aksi or 0)
        lama = k["daily_budget"] or 0
        c.execute("UPDATE campaigns SET daily_budget=?, sinkron_terakhir=datetime('now','localtime') WHERE id=?",
                  (baru, k["id"]))
        return "executed", f"Budget Rp {lama:,.0f} → Rp {baru:,.0f}".replace(",", ".")
    if aksi == "set_status":
        c.execute("UPDATE campaigns SET status=?, sinkron_terakhir=datetime('now','localtime') WHERE id=?",
                  (nilai_aksi, k["id"]))
        return "executed", f"Status → {nilai_aksi}"
    if aksi.startswith("bid_"):
        return "executed", f"Bid keyword disesuaikan {rule['action_value']}% (simulasi)"
    if aksi == "notify":
        return "executed", "Notifikasi analisa terkirim"
    return "executed", f"Aksi {aksi} (simulasi)"


# ------------------------------------------------------------------ live (API)
def _client_untuk(shop_id_ext: str):
    """Bangun ShopeeClient bila shop sudah terotorisasi; None bila belum."""
    import os
    from shopee_connector.client import ShopeeClient
    from shopee_connector.config import Config
    from shopee_connector.token_store import JsonFileTokenStore
    cfg = Config.from_env()
    store = JsonFileTokenStore(cfg.token_dir or os.environ.get("SHOPEE_TOKEN_DIR", "./tokens"))
    try:
        shop_id = int(shop_id_ext)
    except (TypeError, ValueError):
        return None, f"shop_id_ext '{shop_id_ext}' tidak valid"
    if store.load(shop_id) is None:
        return None, "Toko belum diotorisasi — jalankan authorize dulu."
    return ShopeeClient(cfg, store), ""


def _post_ads(client, shop_id: int, path: str, body: dict) -> dict:
    """POST shop-level dengan json_body ke endpoint Ads."""
    token = client.token_store.load(shop_id)
    return client.request("POST", path, json_body=body,
                          access_token=token.access_token, shop_id=shop_id)


def live(c, k, rule, aksi: str, nilai_aksi: str) -> Tuple[str, str]:
    """Eksekusi ke Shopee Ads API. Field body ditandai TODO-verifikasi."""
    # Kebijakan dulu, API belakangan: tolak tulis ke kampanye iklan otomatis
    # (endpointnya dijadwalkan offline oleh Shopee) — berlaku walau kredensial valid.
    if k["type"] == "auto":
        return "blocked", ("Kampanye 'Iklan Produk Otomatis' memakai endpoint yang akan dimatikan "
                           "Shopee — migrasikan ke manual auto-bidding/GMS dulu.")

    try:
        client, err = _client_untuk(k["shop_id_ext"])
    except Exception as e:  # noqa: BLE001 -- mis. env partner belum di-set
        return "blocked", f"API off: {e}"
    if client is None:
        return "blocked", f"API off: {err}"
    shop_id = int(k["shop_id_ext"])

    try:
        if aksi == "set_budget":
            body = {"campaign_id": int(k["ext_id"]), "budget": float(nilai_aksi)}
            # TODO-verifikasi: nama field persis di dok `edit_manual_product_ads`
            # (kemungkinan juga perlu start_date/end_date/roas_target ikut dikirim)
            _post_ads(client, shop_id, "/api/v2/ads/edit_manual_product_ads", body)
            c.execute("UPDATE campaigns SET daily_budget=?, sinkron_terakhir=datetime('now','localtime') WHERE id=?",
                      (float(nilai_aksi), k["id"]))
            return "executed", f"Budget diubah via API → Rp {float(nilai_aksi):,.0f}".replace(",", ".")

        if aksi == "set_status":
            body = {"campaign_id": int(k["ext_id"]), "status": nilai_aksi}
            # TODO-verifikasi: nama field status (ongoing/paused) di dok
            _post_ads(client, shop_id, "/api/v2/ads/edit_manual_product_ads", body)
            c.execute("UPDATE campaigns SET status=?, sinkron_terakhir=datetime('now','localtime') WHERE id=?",
                      (nilai_aksi, k["id"]))
            return "executed", f"Status diubah via API → {nilai_aksi}"

        if aksi.startswith("bid_"):
            # TODO-verifikasi: schema edit_manual_product_ad_keywords (list keyword + bid baru)
            return "blocked", "Bid keyword live menunggu verifikasi schema dok — simulasikan dulu."

        if aksi == "notify":
            return "executed", "Notifikasi analisa terkirim"
        return "blocked", f"Aksi {aksi} belum didukung live."
    except Exception as e:  # noqa: BLE001
        log.exception("API gagal kampanye %s", k["id"])
        return "blocked", f"API error: {e}"
