"""Rules engine Autopilot.

Siklus (tiap `interval_menit`, atau dipicu manual):
  1. Sinkron kampanye+performa (demo generator / API — lihat ads_source.py)
  2. Untuk setiap rule aktif (urut priority) × kampanye dalam scope:
       evaluasi kondisi -> guardrails (kill-switch global/toko, plafon toko,
       max aksi/hari, lantai & plafon budget per kampanye, dry-run per aturan)
       -> eksekusi: DEMO (ubah DB saja, semua aman) / DRYRUN (catat saja) /
          LIVE (panggil API tulis via executor) — notifikasi Telegram.
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from . import db, notify

log = logging.getLogger("autopilot.engine")

OP = {"lt": lambda a, b: a < b, "gt": lambda a, b: a > b,
      "gte": lambda a, b: a >= b, "lte": lambda a, b: a <= b}


def _banding(metric: str, comparator: str, nilai_now: float, nilai_prev: float,
             threshold: float) -> Tuple[bool, str]:
    """Bandingkan metrik vs ambang. comparator drop/rise = perubahan % vs periode sebelumnya."""
    if comparator in OP:
        simbol = {"lt": "<", "gt": ">", "gte": "≥", "lte": "≤"}[comparator]
        return OP[comparator](nilai_now, threshold), f"{metric} {nilai_now:g} {simbol} {threshold:g}"
    if comparator in ("drop", "rise"):
        if nilai_prev <= 0:
            return False, f"{metric}: periode sebelumnya kosong"
        perubahan = (nilai_now - nilai_prev) / nilai_prev * 100
        if comparator == "drop":
            return perubahan <= -threshold, f"{metric} turun {perubahan:.0f}% (ambang -{threshold:g}%)"
        return perubahan >= threshold, f"{metric} naik {perubahan:.0f}% (ambang +{threshold:g}%)"
    return False, f"comparator tak dikenal: {comparator}"


def _nilai(metrik_row: Dict[str, float], metric: str) -> float:
    return float(metrik_row.get(metric, 0) or 0)


def _kampanye_scope(c, rule) -> list:
    """Kampanye target berdasarkan scope rule."""
    if rule["scope_type"] == "store":
        return db.list_campaigns(c, store_id=int(rule["scope_value"] or 0))
    if rule["scope_type"] == "campaign":
        row = db.get_campaign(c, int(rule["scope_value"] or 0))
        return [row] if row else []
    if rule["scope_type"] == "type":
        return db.list_campaigns(c, type_=rule["scope_value"])
    return db.list_campaigns(c)


def _rule_dryrun(rule) -> bool:
    u = rule["dryrun_until"] or ""
    return bool(u) and u > db.now_str()


def jalankan_satu_siklus(c, paksa_evaluasi: bool = True) -> Dict[str, int]:
    """Satu siklus penuh engine. Return ringkasan jumlah aksi."""
    from . import ads_source   # import malas: hindari siklus
    ringkas = {"evaluasi": 0, "terpicu": 0, "eksekusi": 0, "dryrun": 0,
               "throttle": 0, "blocked": 0, "pending": 0}

    # 1) sinkron data kampanye & performa
    ads_source.sinkron_semua(c)

    kill_global = db.is_kill(c)
    mode_global = db.mode(c)                      # demo | live
    for rule in db.list_rules(c):
        if not rule["enabled"]:
            continue
        # demo global -> simulasi tulis DB; live global + aturan masih dry-run -> catat saja
        if mode_global == "demo":
            mode = "demo"
        elif _rule_dryrun(rule):
            mode = "dryrun"
        else:
            mode = "live"
        for k in _kampanye_scope(c, rule):
            if not k:
                continue
            ringkas["evaluasi"] += 1
            # --- kill switch ---
            if kill_global:
                continue
            if not k["autopilot_on"]:
                continue

            # --- evaluasi kondisi ---
            now_w = db.metrik_jendela(c, k["id"], rule["window_days"])
            prev_w = db.metrik_jendela(c, k["id"], rule["window_days"], geser=rule["window_days"])
            ok1, teks1 = _banding(rule["metric"], rule["comparator"],
                                  _nilai(now_w, rule["metric"]), _nilai(prev_w, rule["metric"]),
                                  rule["threshold"])
            teks = teks1
            ok = ok1
            if rule["cond2_metric"]:
                now2 = db.metrik_jendela(c, k["id"], rule["cond2_window"])
                prev2 = db.metrik_jendela(c, k["id"], rule["cond2_window"], geser=rule["cond2_window"])
                ok2, teks2 = _banding(rule["cond2_metric"], rule["cond2_comparator"],
                                      _nilai(now2, rule["cond2_metric"]), _nilai(prev2, rule["cond2_metric"]),
                                      rule["cond2_threshold"])
                ok = ok and ok2
                teks += f"  DAN  {teks2}"
            if not ok:
                continue
            ringkas["terpicu"] += 1

            # --- guardrails ---
            if db.aksi_hari_ini(c, rule["id"], k["id"]) >= rule["max_actions_day"]:
                ringkas["throttle"] += 1
                db.catat(c, k["store_id"], k["id"], rule["id"], mode, teks,
                         json.dumps(now_w), rule["action"], f"{rule['action_value']}%",
                         "throttled", f"Sudah {rule['max_actions_day']}x hari ini (batas).")
                continue

            aksi, nilai_aksi, aksi_label, terblokir = _rancang_aksi(c, k, rule)
            if terblokir:
                ringkas["blocked"] += 1
                db.catat(c, k["store_id"], k["id"], rule["id"], mode, teks,
                         json.dumps(now_w), rule["action"], nilai_aksi,
                         "blocked", terblokir)
                continue

            # --- butuh konfirmasi? ---
            if rule["requires_confirm"]:
                did = db.catat(c, k["store_id"], k["id"], rule["id"], mode, teks,
                               json.dumps(now_w), aksi, nilai_aksi, "pending",
                               aksi_label + " — menunggu persetujuan di Log Keputusan.")
                notify.kirim(c, notify.kirim_aksi(rule["nama"] + " (PERLU KONFIRMASI)",
                                                  k["nama_toko"], k["nama"], aksi_label,
                                                  teks, mode))
                ringkas["pending"] += 1
                _ = did
                continue

            # --- eksekusi ---
            status, detail = _eksekusi(c, k, rule, aksi, nilai_aksi, mode)
            ringkas[{"executed": "eksekusi", "dryrun": "dryrun"}.get(status, "blocked")] += 1
            db.catat(c, k["store_id"], k["id"], rule["id"], mode, teks,
                     json.dumps(now_w), aksi, nilai_aksi, status, detail or aksi_label)
            if rule["notify"] != "silent":
                notify.kirim(c, notify.kirim_aksi(rule["nama"], k["nama_toko"], k["nama"],
                                                  aksi_label, teks, mode))
    c.commit()
    return ringkas


def _rancang_aksi(c, k, rule) -> Tuple[str, str, str, Optional[str]]:
    """Rancang aksi final dgn clamp budget floor/ceiling & plafon toko.
    Return (aksi, nilai_aksi_teks, label, alasan_terblokir|None)."""
    aksi, val = rule["action"], rule["action_value"]
    budget = k["daily_budget"] or 0
    if aksi in ("budget_up", "budget_down"):
        if budget <= 0:
            return aksi, f"{val}%", "", "Budget kampanye unlimited — set budget dulu di Seller Center."
        if aksi == "budget_up":
            baru = budget * (1 + val / 100)
            if rule["budget_ceiling"] > 0 and baru > rule["budget_ceiling"]:
                baru = rule["budget_ceiling"]
            # plafon toko: total budget semua kampanye ongoing tidak boleh melebihi plafon_harian
            if k["plafon_harian"] > 0:
                r = c.execute("""SELECT COALESCE(SUM(daily_budget),0) AS t FROM campaigns
                                 WHERE store_id=? AND status='ongoing' AND id<>?""",
                              (k["store_id"], k["id"])).fetchone()
                if r["t"] + baru > k["plafon_harian"]:
                    baru = k["plafon_harian"] - r["t"]
            baru = max(rule["budget_floor"], baru)
            if baru <= budget:
                return aksi, f"{val}%", "", ("Plafon toko/kampanye sudah tercapai "
                                             "— budget tidak dinaikkan.")
            label = f"Budget Rp {budget:,.0f} → Rp {baru:,.0f} (+{val}%)".replace(",", ".")
            return "set_budget", f"{baru:.0f}", label, None
        baru = max(rule["budget_floor"], budget * (1 - val / 100))
        if abs(baru - budget) < 1:
            return aksi, f"{val}%", "", "Budget sudah di lantai — tidak diubah."
        label = f"Budget Rp {budget:,.0f} → Rp {baru:,.0f} (−{val}%)".replace(",", ".")
        return "set_budget", f"{baru:.0f}", label, None
    if aksi == "pause":
        if k["status"] != "ongoing":
            return aksi, "", "", f"Status saat ini '{k['status']}' (bukan ongoing) — dilewati."
        return "set_status", "paused", "Pause kampanye ⏸", None
    if aksi == "resume":
        if k["status"] != "paused":
            return aksi, "", "", f"Status saat ini '{k['status']}' (bukan paused) — dilewati."
        return "set_status", "ongoing", "Resume kampanye ▶", None
    if aksi in ("bid_up", "bid_down"):
        if k["bidding_method"] != "manual":
            return aksi, f"{val}%", "", "Bidding method bukan 'manual' — bid keyword tidak bisa diubah (atur via roas_target/budget)."
        return aksi, f"{val}%", f"Bid keyword {'+' if aksi=='bid_up' else '−'}{val}%", None
    if aksi == "notify":
        return "notify", "", "Notifikasi analisa saja 🔔", None
    return aksi, f"{val}", "", f"Aksi tak dikenal: {aksi}"


def _eksekusi(c, k, rule, aksi: str, nilai_aksi: str, mode_: str) -> Tuple[str, str]:
    """Eksekusi aksi.

    - demo  : simulasi — mengubah DB lokal agar alur terlihat nyata (saldo asli aman).
    - dryrun: hanya DICATAT — DB maupun API tidak disentuh sama sekali.
    - live  : panggil Shopee Ads API via executor.
    """
    from . import executor
    if mode_ == "dryrun":
        return "dryrun", "DRY-RUN → " + executor.preview(k, rule, aksi, nilai_aksi)
    if mode_ == "demo":
        return executor.simulasi(c, k, rule, aksi, nilai_aksi)
    return executor.live(c, k, rule, aksi, nilai_aksi)


def setujui_pending(c, decision_id: int) -> Tuple[bool, str]:
    """Setujui aksi yang menunggu konfirmasi (dari halaman Log)."""
    d = c.execute("SELECT * FROM decisions WHERE id=? AND status='pending'", (decision_id,)).fetchone()
    if not d:
        return False, "Keputusan tidak ditemukan / sudah diproses."
    if db.is_kill(c):
        return False, "Kill-switch aktif — nonaktifkan dulu untuk mengeksekusi aksi."
    k = db.get_campaign(c, d["campaign_id"])
    if k is None:
        return False, "Kampanye sudah tidak ada."
    rule = db.get_rule(c, d["rule_id"]) if d["rule_id"] else None
    mode_ = db.mode(c)
    if mode_ != "live":
        mode_ = "demo"
    status, detail = _eksekusi(c, k, rule, d["aksi"], d["nilai_aksi"], mode_)
    c.execute("UPDATE decisions SET status=?, detail=detail||' | DISETUJUI → '||?  WHERE id=?",
              (status, detail, decision_id))
    c.commit()
    return True, detail


def tolak_pending(c, decision_id: int) -> bool:
    r = c.execute("UPDATE decisions SET status='rejected', detail=detail||' | DITOLAK user.' WHERE id=? AND status='pending'",
                  (decision_id,))
    c.commit()
    return r.rowcount > 0
