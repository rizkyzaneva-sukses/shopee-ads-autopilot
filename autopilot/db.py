"""Lapisan database SQLite Autopilot + akses data."""
import os
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

_SCHEMA = os.path.join(os.path.dirname(__file__), "schema.sql")
_CONN: Optional[sqlite3.Connection] = None
_PATH: Optional[str] = None


def init(path: str = "autopilot.db") -> sqlite3.Connection:
    global _CONN, _PATH
    if _CONN is not None and _PATH == path:
        return _CONN
    _PATH = path
    _CONN = sqlite3.connect(path, check_same_thread=False)
    _CONN.row_factory = sqlite3.Row
    _CONN.execute("PRAGMA foreign_keys = ON")
    with open(_SCHEMA, encoding="utf-8") as f:
        _CONN.executescript(f.read())
    return _CONN


def conn() -> sqlite3.Connection:
    if _CONN is None:
        return init(os.environ.get("AUTOPILOT_DB", "autopilot.db"))
    return _CONN


# ---------------------------------------------------------------- settings
def get_setting(c: sqlite3.Connection, key: str, default: str = "") -> str:
    r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def set_setting(c: sqlite3.Connection, key: str, value: str) -> None:
    c.execute("INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
              (key, str(value)))


def mode(c: sqlite3.Connection) -> str:
    """demo = simulasi tanpa API; live = eksekusi sungguhan via Shopee API."""
    return get_setting(c, "mode", "demo")


def is_kill(c: sqlite3.Connection) -> bool:
    return get_setting(c, "kill", "0") == "1"


def jendela(c: sqlite3.Connection) -> int:
    try:
        return int(get_setting(c, "interval_menit", "60"))
    except ValueError:
        return 60


# ---------------------------------------------------------------- stores & campaigns
def upsert_store(c: sqlite3.Connection, shop_id_ext: str, nama: str) -> int:
    r = c.execute("SELECT id FROM stores WHERE shop_id_ext=?", (shop_id_ext,)).fetchone()
    if r:
        c.execute("UPDATE stores SET nama=? WHERE id=?", (nama, r["id"]))
        return r["id"]
    return c.execute("INSERT INTO stores(shop_id_ext, nama) VALUES (?,?)", (shop_id_ext, nama)).lastrowid


def list_stores(c: sqlite3.Connection) -> List[sqlite3.Row]:
    return c.execute("""
        SELECT s.*,
          (SELECT COUNT(*) FROM campaigns k WHERE k.store_id=s.id) AS jml_kampanye,
          (SELECT COALESCE(SUM(p.spend),0) FROM perf_daily p JOIN campaigns k ON k.id=p.campaign_id
            WHERE k.store_id=s.id AND p.tanggal >= date('now','-6 day')) AS spend_7d,
          (SELECT COALESCE(SUM(p.gmv),0) FROM perf_daily p JOIN campaigns k ON k.id=p.campaign_id
            WHERE k.store_id=s.id AND p.tanggal >= date('now','-6 day')) AS gmv_7d,
          (SELECT COALESCE(SUM(k.daily_budget),0) FROM campaigns k
            WHERE k.store_id=s.id AND k.status='ongoing') AS budget_aktif
        FROM stores s ORDER BY s.nama""").fetchall()


def upsert_campaign(c: sqlite3.Connection, store_id: int, ext_id: str, nama: str,
                    type_: str = "manual", bidding_method: str = "auto",
                    status: str = "ongoing", daily_budget: float = 0,
                    roas_target: float = 0, start_date: str = "", end_date: str = "") -> int:
    c.execute("""INSERT INTO campaigns(store_id, ext_id, nama, type, bidding_method, status,
                                       daily_budget, roas_target, start_date, end_date)
                 VALUES (?,?,?,?,?,?,?,?,?,?)
                 ON CONFLICT(store_id, ext_id) DO UPDATE SET
                     nama=excluded.nama, type=excluded.type, bidding_method=excluded.bidding_method,
                     status=excluded.status, daily_budget=excluded.daily_budget,
                     roas_target=excluded.roas_target""",
              (store_id, ext_id, nama, type_, bidding_method, status,
               daily_budget, roas_target, start_date, end_date))
    return c.execute("SELECT id FROM campaigns WHERE store_id=? AND ext_id=?",
                     (store_id, ext_id)).fetchone()["id"]


def list_campaigns(c: sqlite3.Connection, store_id: int = 0, type_: str = "",
                   status: str = "") -> List[sqlite3.Row]:
    w, p = ["1=1"], []
    if store_id:
        w.append("k.store_id=?"); p.append(store_id)
    if type_:
        w.append("k.type=?"); p.append(type_)
    if status:
        w.append("k.status=?"); p.append(status)
    return c.execute(f"""
        SELECT k.*, s.nama AS nama_toko, s.autopilot_on, s.plafon_harian, s.shop_id_ext,
          (SELECT COALESCE(SUM(spend),0) FROM perf_daily WHERE campaign_id=k.id
            AND tanggal >= date('now','-6 day')) AS spend_7d,
          (SELECT COALESCE(SUM(gmv),0) FROM perf_daily WHERE campaign_id=k.id
            AND tanggal >= date('now','-6 day')) AS gmv_7d
        FROM campaigns k JOIN stores s ON s.id=k.store_id
        WHERE {' AND '.join(w)} ORDER BY spend_7d DESC""", p).fetchall()


def get_campaign(c: sqlite3.Connection, cid: int) -> Optional[sqlite3.Row]:
    return c.execute("""SELECT k.*, s.nama AS nama_toko, s.autopilot_on, s.plafon_harian,
                               s.shop_id_ext
                        FROM campaigns k JOIN stores s ON s.id=k.store_id WHERE k.id=?""",
                     (cid,)).fetchone()


# ---------------------------------------------------------------- performa
def put_perf(c: sqlite3.Connection, campaign_id: int, tanggal: str, spend: float, gmv: float,
             impresi: int = 0, klik: int = 0, konversi: float = 0) -> None:
    c.execute("""INSERT INTO perf_daily(campaign_id, tanggal, spend, gmv, impresi, klik, konversi)
                 VALUES (?,?,?,?,?,?,?)
                 ON CONFLICT(campaign_id, tanggal) DO UPDATE SET
                     spend=excluded.spend, gmv=excluded.gmv, impresi=excluded.impresi,
                     klik=excluded.klik, konversi=excluded.konversi""",
              (campaign_id, tanggal, spend, gmv, impresi, klik, konversi))


def metrik_jendela(c: sqlite3.Connection, campaign_id: int, window_days: int,
                   geser: int = 0) -> Dict[str, float]:
    """Agregat metrik selama window_days terakhir. geser=window → periode sebelumnya."""
    today = date.today()
    end = today - timedelta(days=geser)
    start = end - timedelta(days=window_days - 1)
    r = c.execute("""SELECT COALESCE(SUM(spend),0) AS spend, COALESCE(SUM(gmv),0) AS gmv,
                            COALESCE(SUM(impresi),0) AS impresi, COALESCE(SUM(klik),0) AS klik,
                            COALESCE(SUM(konversi),0) AS konversi, COUNT(*) AS hari
                     FROM perf_daily WHERE campaign_id=? AND tanggal BETWEEN ? AND ?""",
                  (campaign_id, start.isoformat(), end.isoformat())).fetchone()
    spend, gmv = r["spend"], r["gmv"]
    return {"spend": spend, "gmv": gmv, "impresi": r["impresi"], "klik": r["klik"],
            "konversi": r["konversi"], "hari": r["hari"],
            "roas": (gmv / spend) if spend > 0 else 0.0,
            "ctr": (r["klik"] / r["impresi"] * 100) if r["impresi"] else 0.0,
            "biaya_konversi": (spend / r["konversi"]) if r["konversi"] else 0.0}


def tren(c: sqlite3.Connection, days: int = 14, store_id: int = 0) -> List[Dict[str, Any]]:
    w = "AND k.store_id=?" if store_id else ""
    p: List[Any] = [store_id] if store_id else []
    return [dict(r) for r in c.execute(f"""
        SELECT p.tanggal, SUM(p.spend) AS spend, SUM(p.gmv) AS gmv, SUM(p.klik) AS klik
        FROM perf_daily p JOIN campaigns k ON k.id=p.campaign_id
        WHERE p.tanggal >= date('now', ?) {w}
        GROUP BY p.tanggal ORDER BY p.tanggal""", (f"-{days - 1} day",) + tuple(p)).fetchall()]


# ---------------------------------------------------------------- rules & decisions
def simpan_rule(c: sqlite3.Connection, data: Dict[str, Any], rule_id: int = 0) -> int:
    kolom = ["nama", "enabled", "priority", "scope_type", "scope_value", "metric",
             "window_days", "comparator", "threshold", "cond2_metric", "cond2_comparator",
             "cond2_threshold", "cond2_window", "action", "action_value", "budget_floor",
             "budget_ceiling", "max_actions_day", "requires_confirm", "notify", "dryrun_until"]
    if rule_id:
        sets = ",".join(f"{k}=?" for k in kolom)
        c.execute(f"UPDATE rules SET {sets}, updated_at=datetime('now','localtime') WHERE id=?",
                  [data.get(k) for k in kolom] + [rule_id])
        return rule_id
    cur = c.execute(f"INSERT INTO rules({','.join(kolom)}) VALUES ({','.join('?'*len(kolom))})",
                    [data.get(k) for k in kolom])
    return cur.lastrowid


def get_rule(c: sqlite3.Connection, rid: int) -> Optional[sqlite3.Row]:
    return c.execute("SELECT * FROM rules WHERE id=?", (rid,)).fetchone()


def list_rules(c: sqlite3.Connection) -> List[sqlite3.Row]:
    return c.execute("SELECT * FROM rules ORDER BY priority, id").fetchall()


def aksi_hari_ini(c: sqlite3.Connection, rule_id: int, campaign_id: int) -> int:
    return c.execute("""SELECT COUNT(*) AS n FROM decisions
                        WHERE rule_id=? AND campaign_id=? AND status='executed'
                          AND date(created_at)=date('now','localtime')""",
                     (rule_id, campaign_id)).fetchone()["n"]


def catat(c: sqlite3.Connection, store_id: int, campaign_id: Optional[int],
          rule_id: Optional[int], mode_: str, kondisi: str, nilai_metrik: str,
          aksi: str, nilai_aksi: str, status: str, detail: str = "") -> int:
    return c.execute("""INSERT INTO decisions(store_id, campaign_id, rule_id, mode, kondisi,
                        nilai_metrik, aksi, nilai_aksi, status, detail)
                        VALUES (?,?,?,?,?,?,?,?,?,?)""",
                     (store_id, campaign_id, rule_id, mode_, kondisi, nilai_metrik,
                      aksi, nilai_aksi, status, detail)).lastrowid


def list_decisions(c: sqlite3.Connection, limit: int = 100, store_id: int = 0,
                   status: str = "") -> List[sqlite3.Row]:
    w, p = ["1=1"], []
    if store_id:
        w.append("d.store_id=?"); p.append(store_id)
    if status:
        w.append("d.status=?"); p.append(status)
    return c.execute(f"""
        SELECT d.*, s.nama AS nama_toko, k.nama AS nama_kampanye, r.nama AS nama_rule
        FROM decisions d
        LEFT JOIN stores s ON s.id=d.store_id
        LEFT JOIN campaigns k ON k.id=d.campaign_id
        LEFT JOIN rules r ON r.id=d.rule_id
        WHERE {' AND '.join(w)} ORDER BY d.id DESC LIMIT ?""", p + [limit]).fetchall()


def pending_count(c: sqlite3.Connection) -> int:
    return c.execute("SELECT COUNT(*) AS n FROM decisions WHERE status='pending'").fetchone()["n"]


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
