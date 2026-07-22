"""Lapisan database Autopilot + akses data.

Supports PostgreSQL (primary, via DATABASE_URL) and SQLite (fallback).
When DATABASE_URL env var is set → psycopg2 with RealDictCursor.
Otherwise → sqlite3 with Row factory (local dev).
"""
import os
import re
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

_IS_PG = bool(os.environ.get("DATABASE_URL"))

if _IS_PG:
    import psycopg2
    import psycopg2.extras

_SCHEMA_SQLITE = os.path.join(os.path.dirname(__file__), "schema.sql")
_SCHEMA_PG = os.path.join(os.path.dirname(__file__), "schema_pg.sql")

_CONN: Any = None
_KEY: Optional[str] = None


# ================================================================ SQL conversion for PG
def _convert_pg(sql: str, params) -> Tuple[str, list]:
    """Translate SQLite-flavour SQL + params to PostgreSQL."""
    if params is None:
        params = []
    params = list(params)

    # ? → %s
    sql = sql.replace("?", "%s")

    # datetime('now','localtime') → NOW()
    sql = sql.replace("datetime('now','localtime')", "NOW()")

    # date('now','localtime') → CURRENT_DATE
    sql = sql.replace("date('now','localtime')", "CURRENT_DATE")

    # Hardcoded date intervals: date('now','-N day') → CURRENT_DATE - INTERVAL 'N days'
    def _repl_date(m):
        n = int(m.group(1))
        unit = "day" if abs(n) == 1 else "days"
        return f"(CURRENT_DATE - INTERVAL '{abs(n)} {unit}')::TEXT"
    sql = re.sub(r"date\(\s*'now'\s*,\s*'-(\d+)\s+day'\s*\)", _repl_date, sql)

    # Parameterized date('now', %s) → CURRENT_DATE - INTERVAL 'N days'
    # Process from right-to-left so positions stay valid
    pattern = re.compile(r"date\(\s*'now'\s*,\s*%s\s*\)")
    for match in reversed(list(pattern.finditer(sql))):
        param_idx = sql[: match.start()].count("%s")
        if param_idx < len(params):
            p = params[param_idx]
            if isinstance(p, str) and re.match(r"^-\d+ day$", p):
                n = int(p.split()[0].replace("-", ""))
                unit = "day" if n == 1 else "days"
                sql = sql[: match.start()] + f"(CURRENT_DATE - INTERVAL '{n} {unit}')::TEXT" + sql[match.end() :]
                params.pop(param_idx)

    # Final safety: cast any bare CURRENT_DATE to TEXT for TEXT column comparisons
    sql = sql.replace("CURRENT_DATE)", "CURRENT_DATE::TEXT)")
    # Also handle CURRENT_DATE at end of expressions (not followed by :: already)
    sql = re.sub(r"CURRENT_DATE(?!\s*::)", "CURRENT_DATE::TEXT", sql)
    return sql, params


# ================================================================ cursor / connection wrappers
class _Cursor:
    """Thin wrapper exposing .rowcount, .lastrowid, .fetchone(), .fetchall()."""
    __slots__ = ("_cur", "_lastrowid")

    def __init__(self, raw_cursor, lastrowid=None):
        self._cur = raw_cursor
        self._lastrowid = lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def lastrowid(self):
        return self._lastrowid

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()


class _Conn:
    """Unified connection — wraps sqlite3.Connection or psycopg2 connection.

    Callers see:  .execute(sql, params) → _Cursor
                  .commit()
    """

    def __init__(self, raw, is_pg: bool):
        self._raw = raw
        self._is_pg = is_pg

    def execute(self, sql: str, params=None):
        if self._is_pg:
            sql, params = _convert_pg(sql, params)
            sql_upper = sql.strip().upper()
            is_simple_insert = (
                sql_upper.startswith("INSERT")
                and "ON CONFLICT" not in sql_upper
                and "RETURNING" not in sql_upper
            )
            if is_simple_insert:
                sql = sql.rstrip(";") + " RETURNING id"

            cur = self._raw.cursor()
            cur.execute(sql, params or [])

            lastrowid = None
            if is_simple_insert:
                row = cur.fetchone()
                if row:
                    lastrowid = row["id"] if isinstance(row, dict) else row[0]
            return _Cursor(cur, lastrowid)
        else:
            cur = self._raw.cursor()
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
            return _Cursor(cur, cur.lastrowid)

    def commit(self):
        self._raw.commit()

    def close(self):
        self._raw.close()


# ================================================================ init / conn
def init(path_or_url: str = "autopilot.db"):
    global _CONN, _KEY
    if _CONN is not None and _KEY == path_or_url:
        return _CONN

    if _IS_PG:
        url = os.environ["DATABASE_URL"]
        raw = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
        raw.autocommit = False
        _CONN = _Conn(raw, is_pg=True)
        _KEY = url
        with open(_SCHEMA_PG, encoding="utf-8") as f:
            with raw.cursor() as cur:
                cur.execute(f.read())
        raw.commit()
    else:
        _KEY = path_or_url
        raw = sqlite3.connect(path_or_url, check_same_thread=False)
        raw.row_factory = sqlite3.Row
        raw.execute("PRAGMA foreign_keys = ON")
        _CONN = _Conn(raw, is_pg=False)
        with open(_SCHEMA_SQLITE, encoding="utf-8") as f:
            raw.executescript(f.read())
    return _CONN


def conn():
    if _CONN is None:
        url = os.environ.get("DATABASE_URL")
        if url:
            return init(url)
        return init(os.environ.get("AUTOPILOT_DB", "autopilot.db"))
    return _CONN


# ================================================================ settings
def get_setting(c, key: str, default: str = "") -> str:
    r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def set_setting(c, key: str, value: str) -> None:
    c.execute(
        "INSERT INTO settings(key,value) VALUES (?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )


def mode(c) -> str:
    """demo = simulasi tanpa API; live = eksekusi sungguhan via Shopee API."""
    return get_setting(c, "mode", "demo")


def is_kill(c) -> bool:
    return get_setting(c, "kill", "0") == "1"


def jendela(c) -> int:
    try:
        return int(get_setting(c, "interval_menit", "60"))
    except ValueError:
        return 60


# ================================================================ stores & campaigns
def upsert_store(c, shop_id_ext: str, nama: str) -> int:
    r = c.execute("SELECT id FROM stores WHERE shop_id_ext=?", (shop_id_ext,)).fetchone()
    if r:
        c.execute("UPDATE stores SET nama=? WHERE id=?", (nama, r["id"]))
        return r["id"]
    return c.execute(
        "INSERT INTO stores(shop_id_ext, nama) VALUES (?,?)", (shop_id_ext, nama)
    ).lastrowid


def list_stores(c) -> list:
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


def upsert_campaign(c, store_id: int, ext_id: str, nama: str,
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


def list_campaigns(c, store_id: int = 0, type_: str = "",
                   status: str = "") -> list:
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


def get_campaign(c, cid: int):
    return c.execute("""SELECT k.*, s.nama AS nama_toko, s.autopilot_on, s.plafon_harian,
                               s.shop_id_ext
                        FROM campaigns k JOIN stores s ON s.id=k.store_id WHERE k.id=?""",
                     (cid,)).fetchone()


# ================================================================ performa
def put_perf(c, campaign_id: int, tanggal: str, spend: float, gmv: float,
             impresi: int = 0, klik: int = 0, konversi: float = 0) -> None:
    c.execute("""INSERT INTO perf_daily(campaign_id, tanggal, spend, gmv, impresi, klik, konversi)
                 VALUES (?,?,?,?,?,?,?)
                 ON CONFLICT(campaign_id, tanggal) DO UPDATE SET
                     spend=excluded.spend, gmv=excluded.gmv, impresi=excluded.impresi,
                     klik=excluded.klik, konversi=excluded.konversi""",
              (campaign_id, tanggal, spend, gmv, impresi, klik, konversi))


def metrik_jendela(c, campaign_id: int, window_days: int,
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


def tren(c, days: int = 14, store_id: int = 0) -> List[Dict[str, Any]]:
    w = "AND k.store_id=?" if store_id else ""
    p: List[Any] = [store_id] if store_id else []
    return [dict(r) for r in c.execute(f"""
        SELECT p.tanggal, SUM(p.spend) AS spend, SUM(p.gmv) AS gmv, SUM(p.klik) AS klik
        FROM perf_daily p JOIN campaigns k ON k.id=p.campaign_id
        WHERE p.tanggal >= date('now', ?) {w}
        GROUP BY p.tanggal ORDER BY p.tanggal""",
        (f"-{days - 1} day",) + tuple(p)).fetchall()]


# ================================================================ rules & decisions
def simpan_rule(c, data: Dict[str, Any], rule_id: int = 0) -> int:
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


def get_rule(c, rid: int):
    return c.execute("SELECT * FROM rules WHERE id=?", (rid,)).fetchone()


def list_rules(c) -> list:
    return c.execute("SELECT * FROM rules ORDER BY priority, id").fetchall()


def aksi_hari_ini(c, rule_id: int, campaign_id: int) -> int:
    return c.execute("""SELECT COUNT(*) AS n FROM decisions
                        WHERE rule_id=? AND campaign_id=? AND status='executed'
                          AND date(created_at)=date('now','localtime')""",
                     (rule_id, campaign_id)).fetchone()["n"]


def catat(c, store_id: int, campaign_id, rule_id,
          mode_: str, kondisi: str, nilai_metrik: str,
          aksi: str, nilai_aksi: str, status: str, detail: str = "") -> int:
    return c.execute("""INSERT INTO decisions(store_id, campaign_id, rule_id, mode, kondisi,
                        nilai_metrik, aksi, nilai_aksi, status, detail)
                        VALUES (?,?,?,?,?,?,?,?,?,?)""",
                     (store_id, campaign_id, rule_id, mode_, kondisi, nilai_metrik,
                      aksi, nilai_aksi, status, detail)).lastrowid


def count_decisions(c, store_id: int = 0,
                    status: str = "") -> int:
    w, p = ["1=1"], []
    if store_id:
        w.append("d.store_id=?"); p.append(store_id)
    if status:
        w.append("d.status=?"); p.append(status)
    return c.execute(
        f"SELECT COUNT(*) AS n FROM decisions d WHERE {' AND '.join(w)}", p
    ).fetchone()["n"]


def list_decisions(c, limit: int = 100, store_id: int = 0,
                   status: str = "", offset: int = 0) -> list:
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
        WHERE {' AND '.join(w)} ORDER BY d.id DESC LIMIT ? OFFSET ?""",
        p + [limit, offset]).fetchall()


def pending_count(c) -> int:
    return c.execute(
        "SELECT COUNT(*) AS n FROM decisions WHERE status='pending'"
    ).fetchone()["n"]


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
