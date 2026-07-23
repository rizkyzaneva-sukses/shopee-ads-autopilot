"""Web app Shopee Ads Autopilot (FastAPI, server-rendered).

Jalankan:  python run.py   ->  http://127.0.0.1:8765
"""
import os
from typing import Optional
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from . import db, engine, notify
from .envfile import update_env

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("AUTOPILOT_DB", os.path.join(os.path.dirname(BASE), "autopilot.db"))

app = FastAPI(title="Shopee Ads Autopilot", version="1.0.0")
templates = Jinja2Templates(directory=os.path.join(BASE, "templates"))


def _idr(v) -> str:
    try:
        return f"Rp {float(v or 0):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "-"


templates.env.filters["idr"] = _idr
templates.env.filters["pct"] = lambda v: f"{float(v or 0):.1f}%"
templates.env.filters["g"] = lambda v: f"{float(v or 0):g}"
templates.env.filters["urlencode"] = lambda v: quote(str(v or ""), safe="")



@app.on_event("startup")
def _startup() -> None:
    db.init(DB_PATH)


def _render(request: Request, template: str, **ctx):
    c = db.conn()
    base = {"page": template, "msg": request.query_params.get("msg", ""),
            "bagan": {"pending": db.pending_count(c), "kill": db.is_kill(c),
                      "mode": db.mode(c)}}
    return templates.TemplateResponse(request, f"{template}.html", {**base, **ctx})


def _goto(url: str, msg: str) -> RedirectResponse:
    sep = "&" if "?" in url else "?"
    return RedirectResponse(f"{url}{sep}msg={quote(msg)}", status_code=303)


# ================================================================ MONITORING
@app.get("/", response_class=HTMLResponse)
def monitoring(request: Request, store: int = 0):
    c = db.conn()
    kampanye = db.list_campaigns(c, store_id=store or None)
    tren = db.tren(c, 14, store or None)
    toko = db.list_stores(c)
    # KPI 7 hari semua
    spend7 = sum(k["spend_7d"] or 0 for k in kampanye)
    gmv7 = sum(k["gmv_7d"] or 0 for k in kampanye)
    roas7 = gmv7 / spend7 if spend7 else 0
    return _render(request, "monitoring", kampanye=kampanye, tren=tren, toko=toko,
                   store=store, spend7=spend7, gmv7=gmv7, roas7=roas7,
                   rules=db.list_rules(c), decisions=db.list_decisions(c, 8))


# ================================================================ ATURAN
@app.get("/rules", response_class=HTMLResponse)
def rules_page(request: Request, edit: int = 0):
    c = db.conn()
    rule_edit = db.get_rule(c, edit) if edit else None
    return _render(request, "rules", rules=db.list_rules(c), stores=db.list_stores(c),
                   kampanye=db.list_campaigns(c), edit=rule_edit)


@app.post("/rules/simpan")
async def rule_simpan(request: Request, rule_id: int = Form(0)):
    f = await request.form()
    from datetime import datetime, timedelta
    c = db.conn()
    existing = db.get_rule(c, rule_id) if rule_id else None
    dryrun_baru = (datetime.now() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    if rule_id:
        dryrun_val = "" if f.get("akhiri_dryrun") in ("1", "on") else (f.get("dryrun_until") or "")
    else:
        dryrun_val = dryrun_baru
    data = {
        "nama": (f.get("nama") or "").strip() or "Aturan tanpa nama",
        # enabled tidak di-set via form ini — toggle di tabel; saat edit, pertahankan status lama
        "enabled": (existing["enabled"] if existing else 1),
        "priority": int(f.get("priority") or 50),
        "scope_type": f.get("scope_type", "all"),
        "scope_value": str(f.get("scope_value") or ""),
        "metric": f.get("metric", "roas"),
        "window_days": int(f.get("window_days") or 7),
        "comparator": f.get("comparator", "lt"),
        "threshold": float(f.get("threshold") or 0),
        "cond2_metric": f.get("cond2_metric") or "",
        "cond2_comparator": f.get("cond2_comparator", "gte"),
        "cond2_threshold": float(f.get("cond2_threshold") or 0),
        "cond2_window": int(f.get("cond2_window") or 7),
        "action": f.get("action", "budget_down"),
        "action_value": float(f.get("action_value") or 20),
        "budget_floor": float(f.get("budget_floor") or 20000),
        "budget_ceiling": float(f.get("budget_ceiling") or 0),
        "max_actions_day": int(f.get("max_actions_day") or 2),
        "requires_confirm": 1 if f.get("requires_confirm") in ("1", "on") else 0,
        "notify": f.get("notify", "telegram"),
        "dryrun_until": dryrun_val,
    }
    rid = db.simpan_rule(c, data, rule_id or None)
    c.commit()
    kata = "diperbarui" if rule_id else "ditambahkan (dry-run 24 jam pertama)"
    return _goto("/rules", f"Aturan #{rid} {kata}")


@app.post("/rules/{rule_id}/toggle")
def rule_toggle(rule_id: int):
    c = db.conn()
    r = db.get_rule(c, rule_id)
    if r:
        c.execute("UPDATE rules SET enabled=? WHERE id=?", (0 if r["enabled"] else 1, rule_id))
        c.commit()
        return _goto("/rules", f"Aturan '{r['nama']}' {'diaktifkan' if not r['enabled'] else 'dinonaktifkan'}")
    return _goto("/rules", "Aturan tidak ditemukan")


@app.post("/rules/{rule_id}/hapus")
def rule_hapus(rule_id: int):
    c = db.conn()
    r = db.get_rule(c, rule_id)
    c.execute("DELETE FROM rules WHERE id=?", (rule_id,))
    c.commit()
    return _goto("/rules", f"Aturan '{r['nama'] if r else rule_id}' dihapus")


# ================================================================ LOG KEPUTUSAN
@app.get("/log", response_class=HTMLResponse)
def log_page(request: Request, status: str = "", store: int = 0, page: int = 1):
    c = db.conn()
    per_page = 50
    total = db.count_decisions(c, store or None, status)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page
    return _render(request, "log", decisions=db.list_decisions(c, per_page, store or None, status, offset),
                   stores=db.list_stores(c), store=store, status=status,
                   page=page, total_pages=total_pages)


@app.post("/log/{decision_id}/setujui")
def log_setujui(decision_id: int):
    ok, detail = engine.setujui_pending(db.conn(), decision_id)
    return _goto("/log", ("✅ " + detail) if ok else f"Gagal: {detail}")


@app.post("/log/{decision_id}/tolak")
def log_tolak(decision_id: int):
    ok = engine.tolak_pending(db.conn(), decision_id)
    return _goto("/log", "Ditolak" if ok else "Tidak ditemukan")


# ================================================================ KAMPANYE
@app.get("/kampanye", response_class=HTMLResponse)
def kampanye_page(request: Request, store: int = 0, type_: str = "", status: str = ""):
    c = db.conn()
    return _render(request, "kampanye",
                   kampanye=db.list_campaigns(c, store or None, type_, status),
                   toko=db.list_stores(c), store=store, type_=type_, status=status)


# ================================================================ TOKO
@app.get("/toko", response_class=HTMLResponse)
def toko_page(request: Request):
    c = db.conn()
    info = {s["id"]: db.get_setting(c, f"sync_note_{s['id']}", "-") for s in db.list_stores(c)}
    return _render(request, "toko", toko=db.list_stores(c), sync_note=info)


@app.post("/toko/tambah")
async def toko_tambah(nama: str = Form(...), shop_id_ext: str = Form("")):
    c = db.conn()
    db.upsert_store(c, shop_id_ext.strip() or f"manual-{nama.strip()}", nama.strip())
    c.commit()
    return _goto("/toko", f"Toko '{nama}' ditambahkan")


@app.post("/toko/{store_id}/atur")
async def toko_atur(store_id: int, plafon_harian: str = Form("0"),
                    autopilot_on: Optional[str] = Form(None)):
    c = db.conn()
    c.execute("UPDATE stores SET plafon_harian=?, autopilot_on=? WHERE id=?",
              (float(plafon_harian or 0), 1 if autopilot_on in ("1", "on") else 0, store_id))
    c.commit()
    return _goto("/toko", "Pengaturan toko disimpan")


# ================================================================ OAUTH SHOPEE
@app.get("/auth/shopee/connect", response_class=HTMLResponse)
def auth_shopee_connect(request: Request, nama: str = ""):
    """Memulai alur OAuth Shopee — redirect ke halaman login seller Shopee."""
    partner_id = os.environ.get("SHOPEE_PARTNER_ID", "").strip()
    partner_key = os.environ.get("SHOPEE_PARTNER_KEY", "").strip()
    if not partner_id or not partner_key:
        return _goto("/settings", "⚠️ Isi SHOPEE_PARTNER_ID & SHOPEE_PARTNER_KEY di Settings terlebih dahulu")

    # Simpan nama toko sementara di session via query param (aman utk single-user)
    redirect_url = os.environ.get("SHOPEE_REDIRECT_URL", "").strip()
    if not redirect_url:
        redirect_url = str(request.base_url).rstrip("/") + "/auth/shopee/callback"

    try:
        from shopee_connector.config import Config
        from shopee_connector.client import ShopeeClient
        from shopee_connector.token_store import JsonFileTokenStore
        from shopee_connector import auth as shopee_auth

        cfg = Config(
            partner_id=int(partner_id),
            partner_key=partner_key,
            base_url=os.environ.get("SHOPEE_BASE_URL", "https://partner.shopeemobile.com").rstrip("/"),
            redirect_url=redirect_url,
            token_dir=os.environ.get("SHOPEE_TOKEN_DIR", "./tokens"),
        )
        auth_url = shopee_auth.build_authorization_url(cfg)
        # Simpan nama toko sementara di state (tempelkan ke redirect URL via query)
        if nama:
            auth_url += f"&state={quote(nama, safe='')}"
        return RedirectResponse(auth_url)
    except Exception as exc:
        return _goto("/toko", f"Gagal membuat URL otorisasi: {exc}")


@app.get("/auth/shopee/callback", response_class=HTMLResponse)
def auth_shopee_callback(request: Request, code: str = "", shop_id: str = "", state: str = "", error: str = ""):
    """Callback OAuth dari Shopee — tukar code → token → daftarkan toko."""
    if error:
        return _goto("/toko", f"❌ Otorisasi dibatalkan atau gagal: {error}")
    if not code or not shop_id:
        return _goto("/toko", "❌ Parameter code/shop_id tidak lengkap dari Shopee callback")

    partner_id = os.environ.get("SHOPEE_PARTNER_ID", "").strip()
    partner_key = os.environ.get("SHOPEE_PARTNER_KEY", "").strip()
    if not partner_id or not partner_key:
        return _goto("/settings", "⚠️ Kredensial API belum di-set — isi di Settings")

    redirect_url = os.environ.get("SHOPEE_REDIRECT_URL", "").strip()
    if not redirect_url:
        redirect_url = str(request.base_url).rstrip("/") + "/auth/shopee/callback"

    try:
        from shopee_connector.config import Config
        from shopee_connector.client import ShopeeClient
        from shopee_connector.token_store import JsonFileTokenStore
        from shopee_connector import auth as shopee_auth
        import time

        cfg = Config(
            partner_id=int(partner_id),
            partner_key=partner_key,
            base_url=os.environ.get("SHOPEE_BASE_URL", "https://partner.shopeemobile.com").rstrip("/"),
            redirect_url=redirect_url,
            token_dir=os.environ.get("SHOPEE_TOKEN_DIR", "./tokens"),
        )
        token_store = JsonFileTokenStore(cfg.token_dir)
        client = ShopeeClient(cfg, token_store)

        token = shopee_auth.get_access_token(client, code, shop_id=int(shop_id))
        token_store.save(int(shop_id), token)

        # Daftarkan / perbarui nama toko di database Autopilot
        nama = state.strip() or f"Toko {shop_id}"
        c = db.conn()
        db.upsert_store(c, str(shop_id), nama)
        c.commit()

        expires_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(token.expires_at))
        return _goto("/toko", f"✅ Toko '{nama}' (shop_id {shop_id}) berhasil dihubungkan! Token berlaku s/d {expires_str} (refresh otomatis).")
    except Exception as exc:
        return _goto("/toko", f"❌ Gagal menukar token: {exc}")


# ================================================================ KONTROL
@app.post("/kontrol/siklus")
def kontrol_siklus():
    r = engine.jalankan_satu_siklus(db.conn())
    return _goto("/log", f"Siklus selesai — evaluasi {r['evaluasi']}, terpicu {r['terpicu']}, "
                         f"eksekusi {r['eksekusi']}, dry-run {r['dryrun']}, "
                         f"throttle {r['throttle']}, blocked {r['blocked']}, pending {r['pending']}")


@app.post("/kontrol/kill")
def kontrol_kill():
    c = db.conn()
    kini = db.is_kill(c)
    db.set_setting(c, "kill", "0" if kini else "1")
    c.commit()
    return _goto("/", "⛔ KILL-SWITCH AKTIF — semua aksi dihentikan" if not kini
                 else "✅ Autopilot dilanjutkan")


@app.post("/kontrol/mode/{mode_}")
def kontrol_mode(mode_: str):
    if mode_ not in ("demo", "live"):
        return _goto("/settings", "Mode tidak dikenal")
    c = db.conn()
    db.set_setting(c, "mode", mode_)
    c.commit()
    if mode_ == "live":
        notify.kirim(c, "🤖 Autopilot: mode LIVE diaktifkan — aksi akan dieksekusi ke Shopee API.")
    return _goto("/settings", f"Mode diubah ke {mode_.upper()}")


# ================================================================ PANDUAN
@app.get("/panduan", response_class=HTMLResponse)
def panduan_page(request: Request):
    c = db.conn()
    base = {"page": "panduan", "msg": request.query_params.get("msg", ""),
            "bagan": {"pending": db.pending_count(c), "kill": db.is_kill(c),
                      "mode": db.mode(c)}}
    resp = templates.TemplateResponse(request, "panduan.html", base)
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


# ================================================================ SETTINGS
@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    c = db.conn()
    keys = ["tg_token", "tg_chat_id", "interval_menit"]
    return _render(request, "settings", s={k: db.get_setting(c, k, "") for k in keys},
                   mode=db.mode(c),
                   env_ready=bool(os.environ.get("SHOPEE_PARTNER_ID") and
                                  os.environ.get("SHOPEE_PARTNER_KEY")),
                   base_url=os.environ.get("SHOPEE_BASE_URL", "https://partner.shopeemobile.com"),
                   shopee_partner_id=os.environ.get("SHOPEE_PARTNER_ID", ""),
                   shopee_partner_key=os.environ.get("SHOPEE_PARTNER_KEY", ""),
                   shopee_redirect_url=os.environ.get("SHOPEE_REDIRECT_URL", ""),
                   shopee_base_url_env=os.environ.get("SHOPEE_BASE_URL", "https://partner.shopeemobile.com"))


@app.post("/settings")
async def settings_simpan(tg_token: str = Form(""), tg_chat_id: str = Form(""),
                          interval_menit: str = Form("60")):
    c = db.conn()
    db.set_setting(c, "tg_token", tg_token.strip())
    db.set_setting(c, "tg_chat_id", tg_chat_id.strip())
    db.set_setting(c, "interval_menit", interval_menit.strip() or "60")
    c.commit()
    return _goto("/settings", "Settings tersimpan")


@app.post("/settings/kredensial")
async def settings_kredensial_simpan(
    shopee_partner_id: str = Form(""),
    shopee_partner_key: str = Form(""),
    shopee_redirect_url: str = Form(""),
    shopee_base_url: str = Form("https://partner.shopeemobile.com"),
):
    """Simpan kredensial Shopee Open Platform ke file .env dan os.environ."""
    updates = {
        "SHOPEE_PARTNER_ID": shopee_partner_id.strip(),
        "SHOPEE_PARTNER_KEY": shopee_partner_key.strip(),
        "SHOPEE_REDIRECT_URL": shopee_redirect_url.strip(),
        "SHOPEE_BASE_URL": shopee_base_url.strip() or "https://partner.shopeemobile.com",
    }
    update_env({k: v for k, v in updates.items() if v})
    ready = bool(updates["SHOPEE_PARTNER_ID"] and updates["SHOPEE_PARTNER_KEY"])
    msg = "✅ Kredensial Shopee tersimpan ke .env — siap untuk hubungkan toko" if ready else "Kredensial disimpan (Partner ID/KEY masih kosong)"
    return _goto("/settings", msg)


@app.post("/settings/tes-telegram")
def tes_telegram():
    ok = notify.kirim(db.conn(), "✅ Uji Telegram dari Ads Autopilot berhasil!")
    return _goto("/settings", "Terkirim — cek Telegram Anda ✅" if ok
                 else "Gagal terkirim — periksa token/chat_id (pesan dicatat di log console)")


@app.get("/health")
def health():
    return {"status": "ok", "app": "ads-autopilot", "version": "1.0.0",
            "mode": db.mode(db.conn()), "kill": db.is_kill(db.conn())}
