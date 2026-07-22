# -*- coding: utf-8 -*-
"""Smoke tests Shopee Ads Autopilot — semua jalan offline (tanpa API Shopee).

Jalankan:  python -m pytest tests/ -v
"""
import os
import sys
import tempfile
from datetime import date, timedelta

# --- database uji di file temporer SEBELUM modul app diimpor ---
_TMP = tempfile.mkdtemp(prefix="autopilot_test_")
os.environ["AUTOPILOT_DB"] = os.path.join(_TMP, "test.db")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient          # noqa: E402

from autopilot import db, engine                    # noqa: E402
from autopilot.web import app                       # noqa: E402


def _mk_toko(shop_ext="t-1", nama="Toko Uji", plafon=0):
    c = db.conn()
    sid = db.upsert_store(c, shop_ext, nama)
    c.execute("UPDATE stores SET plafon_harian=? WHERE id=?", (plafon, sid))
    c.commit()
    return sid


def _mk_kampanye(sid, ext="k1", nama="Kampanye Uji", tipe="manual", bidding="auto",
                 status="ongoing", budget=100_000):
    c = db.conn()
    cid = db.upsert_campaign(c, sid, ext, nama, type_=tipe, bidding_method=bidding,
                             status=status, daily_budget=budget)
    c.commit()
    return cid


def _isi_perf(cid, spend_per_hari, roas, hari=14):
    """Data performa deterministik: 14 hari ke belakang."""
    c = db.conn()
    for i in range(hari, 0, -1):
        tgl = (date.today() - timedelta(days=i)).isoformat()
        db.put_perf(c, cid, tgl, spend=spend_per_hari, gmv=spend_per_hari * roas,
                    impresi=10000, klik=200, konversi=2)
    c.commit()


def _buat_rule(c, **kw):
    base = dict(nama="Rule Uji", enabled=1, priority=50, scope_type="all", scope_value="",
                metric="roas", window_days=7, comparator="lt", threshold=99,
                cond2_metric="", cond2_comparator="gte", cond2_threshold=0, cond2_window=7,
                action="budget_down", action_value=20, budget_floor=20_000, budget_ceiling=0,
                max_actions_day=2, requires_confirm=0, notify="silent", dryrun_until="")
    base.update(kw)
    return db.simpan_rule(c, base)


def _bersih():
    """Reset database ke kondisi kosong & mode demo."""
    c = db.conn()
    for t in ("decisions", "rules", "perf_daily", "campaigns", "stores"):
        c.execute(f"DELETE FROM {t}")
    db.set_setting(c, "mode", "demo")
    db.set_setting(c, "kill", "0")
    c.commit()


# ================================================================ halaman web
def test_semua_halaman_200():
    with TestClient(app) as client:
        for path in ("/", "/rules", "/log", "/kampanye", "/toko", "/settings", "/health"):
            r = client.get(path)
            assert r.status_code == 200, f"{path} -> {r.status_code}"


def test_health_json():
    with TestClient(app) as client:
        j = client.get("/health").json()
        assert j["status"] == "ok" and j["app"] == "ads-autopilot"


# ================================================================ engine dasar
def test_siklus_demo_menurunkan_budget_boncos():
    _bersih()
    sid = _mk_toko()
    cid = _mk_kampanye(sid, budget=100_000)
    _isi_perf(cid, spend_per_hari=50_000, roas=0.5)          # ROAS 0.5 -> boncos
    c = db.conn()
    _buat_rule(c, nama="Rem boncos", metric="roas", threshold=1.0, action="budget_down",
               action_value=50, budget_floor=20_000)
    c.commit()
    ringkas = engine.jalankan_satu_siklus(c)
    assert ringkas["terpicu"] == 1 and ringkas["eksekusi"] == 1
    k = db.get_campaign(c, cid)
    assert k["daily_budget"] == 50_000                       # 100rb * (1-50%)
    d = db.list_decisions(c, 10)
    assert d and d[0]["status"] == "executed" and d[0]["mode"] == "demo"


def test_lantai_budget_dihormati():
    _bersih()
    sid = _mk_toko()
    cid = _mk_kampanye(sid, budget=25_000)
    _isi_perf(cid, 50_000, roas=0.5)
    c = db.conn()
    _buat_rule(c, threshold=1.0, action="budget_down", action_value=50, budget_floor=20_000)
    c.commit()
    r = engine.jalankan_satu_siklus(c)
    # 25rb * 0.5 = 12.5rb -> di-clamp ke lantai 20rb -> masih dieksekusi (25rb -> 20rb)
    assert r["eksekusi"] == 1
    assert db.get_campaign(c, cid)["daily_budget"] == 20_000


def test_plafon_toko_memblokir_kenaikan_budget():
    _bersih()
    sid = _mk_toko(plafon=150_000)
    _mk_kampanye(sid, ext="k1", budget=100_000)
    cid2 = _mk_kampanye(sid, ext="k2", budget=50_000)
    _isi_perf(cid2, 10_000, roas=9.0)                        # ROAS tinggi → aturan naik
    c = db.conn()
    _buat_rule(c, metric="roas", comparator="gte", threshold=3, action="budget_up",
               action_value=100)                             # 50rb -> 100rb, tapi 100+100 > 150 plafon
    c.commit()
    r = engine.jalankan_satu_siklus(c)
    assert r["terpicu"] == 1 and r["blocked"] == 1           # kenaikan diblokir guardrail
    assert db.get_campaign(c, cid2)["daily_budget"] == 50_000


def test_throttle_maks_aksi_per_hari():
    _bersih()
    sid = _mk_toko()
    cid = _mk_kampanye(sid, budget=200_000)
    _isi_perf(cid, 50_000, roas=0.5)
    c = db.conn()
    _buat_rule(c, threshold=1.0, action="budget_down", action_value=10,
               budget_floor=10_000, max_actions_day=1)
    c.commit()
    r1 = engine.jalankan_satu_siklus(c)
    r2 = engine.jalankan_satu_siklus(c)
    assert r1["eksekusi"] == 1 and r2["throttle"] == 1


def test_kill_switch_menghentikan_semua_aksi():
    _bersih()
    sid = _mk_toko()
    cid = _mk_kampanye(sid, budget=100_000)
    _isi_perf(cid, 50_000, roas=0.5)
    c = db.conn()
    _buat_rule(c, threshold=1.0, action="budget_down", action_value=50)
    db.set_setting(c, "kill", "1")
    c.commit()
    r = engine.jalankan_satu_siklus(c)
    assert r["terpicu"] == 0 and r["eksekusi"] == 0
    assert db.get_campaign(c, cid)["daily_budget"] == 100_000   # tak tersentuh
    assert db.pending_count(c) == 0


def test_toko_autopilot_off_dilewati():
    _bersih()
    sid = _mk_toko()
    cid = _mk_kampanye(sid, budget=100_000)
    _isi_perf(cid, 50_000, roas=0.5)
    c = db.conn()
    c.execute("UPDATE stores SET autopilot_on=0 WHERE id=?", (sid,))
    _buat_rule(c, threshold=1.0)
    c.commit()
    r = engine.jalankan_satu_siklus(c)
    assert r["terpicu"] == 0
    assert db.get_campaign(c, cid)["daily_budget"] == 100_000


def test_aturan_baru_dryrun_di_mode_live():
    _bersih()
    sid = _mk_toko()
    cid = _mk_kampanye(sid, budget=100_000)
    _isi_perf(cid, 50_000, roas=0.5)
    c = db.conn()
    dari = (date.today() + timedelta(days=1)).isoformat() + " 00:00:00"
    _buat_rule(c, threshold=1.0, action="budget_down", action_value=50, dryrun_until=dari)
    db.set_setting(c, "mode", "live")                        # live global, aturan masih dry-run
    c.commit()
    r = engine.jalankan_satu_siklus(c)
    assert r["dryrun"] == 1 and r["eksekusi"] == 0
    assert db.get_campaign(c, cid)["daily_budget"] == 100_000   # dry-run TIDAK mengubah apa pun
    assert db.list_decisions(c, 5)[0]["status"] == "dryrun"


def test_konfirmasi_pending_lalu_disetujui():
    _bersih()
    sid = _mk_toko()
    cid = _mk_kampanye(sid, budget=100_000)
    _isi_perf(cid, 50_000, roas=0.5)
    c = db.conn()
    _buat_rule(c, threshold=1.0, action="budget_down", action_value=50, requires_confirm=1)
    c.commit()
    r = engine.jalankan_satu_siklus(c)
    assert r["pending"] == 1 and r["eksekusi"] == 0
    assert db.get_campaign(c, cid)["daily_budget"] == 100_000
    did = db.pending_count(c) and db.list_decisions(c, 1, status="pending")[0]["id"]
    ok, _ = engine.setujui_pending(c, did)
    assert ok
    assert db.get_campaign(c, cid)["daily_budget"] == 50_000    # demo: dieksekusi setelah setuju


def test_pending_ditolak_tidak_mengubah_apapun():
    _bersih()
    sid = _mk_toko()
    cid = _mk_kampanye(sid, budget=100_000)
    _isi_perf(cid, 50_000, roas=0.5)
    c = db.conn()
    _buat_rule(c, threshold=1.0, action="budget_down", action_value=50, requires_confirm=1)
    c.commit()
    engine.jalankan_satu_siklus(c)
    did = db.list_decisions(c, 1, status="pending")[0]["id"]
    assert engine.tolak_pending(c, did)
    assert db.get_campaign(c, cid)["daily_budget"] == 100_000


def test_pause_resume_flow():
    _bersih()
    sid = _mk_toko()
    cid = _mk_kampanye(sid, budget=100_000)
    _isi_perf(cid, 50_000, roas=0.5)
    c = db.conn()
    _buat_rule(c, threshold=1.0, action="pause")
    c.commit()
    engine.jalankan_satu_siklus(c)
    assert db.get_campaign(c, cid)["status"] == "paused"


def test_kampanye_auto_diblokir_di_live():
    _bersih()
    sid = _mk_toko()
    cid = _mk_kampanye(sid, tipe="auto", budget=100_000)
    _isi_perf(cid, 50_000, roas=0.5)
    c = db.conn()
    _buat_rule(c, threshold=1.0, action="budget_down", action_value=50)
    db.set_setting(c, "mode", "live")
    c.commit()
    r = engine.jalankan_satu_siklus(c)
    assert r["blocked"] == 1                                    # endpoint auto deprecated -> tolak
    assert db.get_campaign(c, cid)["daily_budget"] == 100_000
    assert "Otomatis" in db.list_decisions(c, 1)[0]["detail"]


# ================================================================ via HTTP
def test_crud_aturan_via_http():
    _bersih()
    with TestClient(app) as client:
        # buat aturan baru lewat form
        r = client.post("/rules/simpan", data={
            "nama": "Aturan via HTTP", "priority": "30", "scope_type": "all",
            "metric": "roas", "window_days": "7", "comparator": "lt", "threshold": "1.5",
            "cond2_metric": "", "action": "budget_down", "action_value": "25",
            "budget_floor": "20000", "budget_ceiling": "0", "max_actions_day": "2",
            "notify": "telegram",
        }, follow_redirects=False)
        assert r.status_code == 303
        info = {row["id"]: row for row in db.list_rules(db.conn())}
        assert info, "aturan tidak tersimpan"
        rid = next(iter(info))
        assert info[rid]["nama"] == "Aturan via HTTP"
        assert info[rid]["dryrun_until"]                      # aturan baru auto dry-run 24 jam

        # toggle off lalu hapus
        assert client.post(f"/rules/{rid}/toggle", follow_redirects=False).status_code == 303
        assert db.get_rule(db.conn(), rid)["enabled"] == 0
        assert client.post(f"/rules/{rid}/hapus", follow_redirects=False).status_code == 303
        assert db.get_rule(db.conn(), rid) is None


def test_kontrol_siklus_via_http_dan_kill():
    _bersih()
    sid = _mk_toko()
    cid = _mk_kampanye(sid, budget=100_000)
    _isi_perf(cid, 50_000, roas=0.5)
    c = db.conn()
    _buat_rule(c, threshold=1.0, action="budget_down", action_value=50)
    c.commit()
    with TestClient(app) as client:
        r = client.post("/kontrol/siklus", follow_redirects=False)
        assert r.status_code == 303
        assert db.get_campaign(c, cid)["daily_budget"] == 50_000

        # kill-switch via HTTP memblokir siklus berikutnya
        assert client.post("/kontrol/kill", follow_redirects=False).status_code == 303
        r = client.post("/kontrol/siklus", follow_redirects=True)
        assert r.status_code == 200
        assert db.get_campaign(c, cid)["daily_budget"] == 50_000   # tidak turun lagi
        assert client.post("/kontrol/kill", follow_redirects=False).status_code == 303  # buka lagi


def test_settings_dan_mode_via_http(monkeypatch):
    _bersih()

    class _Resp:  # respons Telegram palsu agar tes 100% offline
        ok = True
        text = "{}"
        def json(self):
            return {"ok": True}

    import autopilot.notify as notify_mod
    monkeypatch.setattr(notify_mod.requests, "post", lambda *a, **kw: _Resp())

    with TestClient(app) as client:
        r = client.post("/settings", data={"tg_token": "x", "tg_chat_id": "y",
                                           "interval_menit": "120"}, follow_redirects=False)
        assert r.status_code == 303
        c = db.conn()
        assert db.get_setting(c, "tg_token") == "x"
        assert db.jendela(c) == 120
        assert client.post("/kontrol/mode/live", follow_redirects=False).status_code == 303
        assert db.mode(c) == "live"
        assert client.post("/kontrol/mode/demo", follow_redirects=False).status_code == 303
        assert db.mode(c) == "demo"
        assert client.post("/settings/tes-telegram", follow_redirects=False).status_code == 303


def test_tambah_toko_dan_atur_plafon_via_http():
    _bersih()
    with TestClient(app) as client:
        r = client.post("/toko/tambah", data={"nama": "Cabang Uji", "shop_id_ext": ""},
                        follow_redirects=False)
        assert r.status_code == 303
        sid = db.list_stores(db.conn())[0]["id"]
        r = client.post(f"/toko/{sid}/atur", data={"plafon_harian": "250000"},
                        follow_redirects=False)
        assert r.status_code == 303
        s = db.list_stores(db.conn())[0]
        assert s["plafon_harian"] == 250_000 and s["autopilot_on"] == 0  # checkbox off -> 0
