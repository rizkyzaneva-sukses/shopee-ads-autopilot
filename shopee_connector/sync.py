"""Orkestrasi sinkronisasi inkremental per toko.

Strategi:
- get_order_list dibatasi rentang 15 hari -> pecah jadi jendela 14 hari.
- Inkremental berdasarkan `update_time` agar pesanan yang berubah status
  (mis. PACKED -> COMPLETED) ikut tertarik di sync berikutnya.
- Escrow ditarik hanya untuk pesanan COMPLETED (escrow memang baru ada saat selesai).
- SEMUA respons disimpan mentah sebagai JSON (raw payload) sebelum dinormalisasi.
- Watermark terakhir disimpan di file state -> sync berikutnya mulai dari situ.

Produksi: jalankan via cron/queue worker; ganti file CSV dengan insert ke
PostgreSQL (lihat db/schema.sql, tabel orders/order_fees/raw_payloads).
"""
import csv
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple

from . import api, normalize
from .client import ShopeeClient

log = logging.getLogger("shopee_connector.sync")

WINDOW_SECONDS = 14 * 24 * 3600      # aman di bawah batas 15 hari
OVERLAP_SECONDS = 5 * 60             # watermark mundur 5 menit -> anti jeda data


@dataclass
class SyncStats:
    shop_id: int
    started_at: int = 0
    finished_at: int = 0
    windows: int = 0
    orders_found: int = 0
    details_fetched: int = 0
    escrow_fetched: int = 0
    fee_rows: int = 0


def _save_json(dirpath: str, name: str, obj: Any) -> None:
    os.makedirs(dirpath, exist_ok=True)
    with open(os.path.join(dirpath, name), "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _state_file(state_dir: str, shop_id: int) -> str:
    os.makedirs(state_dir, exist_ok=True)
    return os.path.join(state_dir, f"shop_{shop_id}.json")


def load_state(state_dir: str, shop_id: int) -> Optional[Dict[str, Any]]:
    path = _state_file(state_dir, shop_id)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def save_state(state_dir: str, shop_id: int, state: Dict[str, Any]) -> None:
    with open(_state_file(state_dir, shop_id), "w") as f:
        json.dump(state, f, indent=2)


def iter_windows(since_ts: int, until_ts: int) -> Iterator[Tuple[int, int]]:
    start = since_ts
    while start < until_ts:
        end = min(start + WINDOW_SECONDS, until_ts)
        yield start, end
        start = end


def _append_fee_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    exists = os.path.exists(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["order_sn", "jenis_fee", "label", "jumlah", "field_asal"])
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def sync_shop(client: ShopeeClient, shop_id: int, since_ts: int, raw_dir: str,
              state_dir: str, until_ts: Optional[int] = None,
              fee_csv: Optional[str] = None) -> SyncStats:
    until_ts = until_ts or int(time.time())
    raw_shop = os.path.join(raw_dir, str(shop_id))
    stats = SyncStats(shop_id=shop_id, started_at=int(time.time()))
    log.info("Mulai sync shop=%s dari=%s sampai=%s", shop_id, since_ts, until_ts)

    for w_from, w_to in iter_windows(since_ts, until_ts):
        stats.windows += 1
        entries = api.list_order_sn(client, shop_id, w_from, w_to, time_range_field="update_time")
        stats.orders_found += len(entries)
        if not entries:
            continue

        all_sn = [e["order_sn"] for e in entries]
        completed_sn = [e["order_sn"] for e in entries if e.get("order_status") == "COMPLETED"]
        log.info("  jendela %s-%s: %s order (%s selesai)", w_from, w_to, len(all_sn), len(completed_sn))

        # 1) detail order -> raw + (hook insert ke tabel `orders`)
        details = api.get_order_detail(client, shop_id, all_sn)
        for d in details:
            _save_json(os.path.join(raw_shop, "orders"), f"{d['order_sn']}.json", d)
            # TODO produksi: upsert normalize.order_to_summary(d) -> tabel orders
        stats.details_fetched += len(details)

        # 2) escrow batch untuk pesanan selesai -> raw + baris fee
        escrows = api.get_escrow_detail_batch(client, shop_id, completed_sn) if completed_sn else []
        fee_rows: List[Dict[str, Any]] = []
        for e in escrows:
            sn = e.get("order_sn")
            if not sn:
                continue
            _save_json(os.path.join(raw_shop, "escrow"), f"{sn}.json", e)
            fee_rows.extend(normalize.escrow_to_fee_rows(sn, e)["fees"])
        stats.escrow_fetched += len(escrows)
        stats.fee_rows += len(fee_rows)
        if fee_csv:
            _append_fee_csv(fee_csv, fee_rows)  # TODO produksi: insert -> order_fees

    save_state(state_dir, shop_id, {"last_update_to": until_ts - OVERLAP_SECONDS,
                                    "synced_at": until_ts})
    stats.finished_at = int(time.time())
    log.info("Selesai sync shop=%s: %s", shop_id, stats)
    return stats
