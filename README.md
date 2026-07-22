# 🤖 Shopee Ads Autopilot

Autopilot iklan Shopee milik Anda sendiri — **aturan otomatis** untuk menaikkan/menurunkan
budget, pause/resume kampanye, dan penyesuaian bid, berdasarkan performa nyata.
Multi-toko (semua cabang dalam satu dashboard), notifikasi Telegram, dan dirancang
**aman-by-default**: mode demo, dry-run otomatis, plafon, throttle, dan kill-switch.

- Tanpa langganan SaaS. Database lokal (SQLite). Jalan di PC Windows 24 jam.
- Semua aksi tulis hanya lewat **Shopee Open Platform API v2 resmi**.
- Default pertama kali jalan: **MODE DEMO** (simulasi) — saldo iklan 100% aman.

---

## 1. Instalasi & menjalankan (Windows)

```bat
cd folder-aplikasi
python -m pip install -r requirements.txt
python scripts\seed_demo.py        :: isi data demo (6 toko, 30 kampanye, 30 hari performa)
python run.py                      :: server + scheduler otomatis
```

Buka dashboard: **http://127.0.0.1:8765**

Untuk menjalan ulang demo dari nol: `python scripts\seed_demo.py --reset`

> Python 3.10+ disarankan. Tidak butuh Docker/Node/dsb.

## 2. Mode operasi

| Mode | Perilaku | Kapan dipakai |
|---|---|---|
| **DEMO** 🛡️ | Semua aksi *disimulasikan* di database lokal (budget/status tampak berubah di dashboard), **tidak ada panggilan API tulis** | Saat menyiapkan aturan & memvalidasi logika |
| **DRY-RUN** ⏳ | Otomatis: aturan baru di mode LIVE tetap hanya *dievaluasi & dicatat* selama **24 jam pertama** (bisa diakhiri lebih awal saat mengubah aturan) | Masa uji coba aturan baru |
| **LIVE** 🔴 | Aksi dieksekusi sungguhan via Shopee Ads API | Setelah data nyata & field API tervalidasi |

Rem darurat berlapis (selalu aktif, semua mode):

- ⛔ **Kill-switch** global di pojok kanan atas — hentikan SEMUA aksi dalam 1 klik.
- 🏪 **Autopilot per toko** bisa dimatikan (halaman Toko).
- 💰 **Plafon harian per toko** — total budget kampanye ongoing tidak akan melewati batas ini.
- 📉 **Lantai & plafon budget per kampanye** di setiap aturan.
- 🔁 **Maks aksi/hari per kampanye** (anti-oscilasi).
- ✋ **Minta konfirmasi** — aksi menunggu persetujuan Anda di Log Keputusan.

Semua keputusan tercatat permanen di **Log Keputusan** (kondisi, snapshot metrik, aksi, hasil).

## 3. Menyusun aturan

Halaman **Aturan** → form bawah. Contoh klasik yang sudah dibuatkan `seed_demo.py`:

| Aturan | Kondisi | Aksi | Pengaman |
|---|---|---|---|
| Rem kampanye boncos | ROAS 7h < 1 **dan** spend 7h ≥ Rp100rb | Budget −30% | lantai Rp20rb, 1×/hari |
| Gas kampanye juara | ROAS 7h ≥ 3 (tipe manual) | Budget +20% | plafon Rp500rb/kampanye |
| Pause total boncos | ROAS 14h < 0,5 | ⏸ Pause | **minta konfirmasi** |
| Pengingat migrasi | spend iklan otomatis 7h > Rp50rb | 🔔 Notif saja | — |

Pembanding `drop`/`rise` membandingkan persen perubahan vs **periode sebelumnya**
(mis. ROAS 7 hari ini turun > 30% dibanding 7 hari sebelumnya).

## 4. Penjadwalan di PC Windows 24 jam

**Cara utama (disarankan):** biarkan `python run.py` menyala — scheduler thread bawaan
menjalankan siklus tiap `interval_menit` (default 60, ubah di Settings). Interval dibaca
ulang tiap putaran, jadi perubahan di Settings langsung dipakai.

**Alternatif — Windows Task Scheduler** (bila web server tidak selalu nyala):

```bat
schtasks /create /tn "ShopeeAdsAutopilot" ^
  /tr "\"C:\Users\Anda\AppData\Local\Programs\Python\Python313\python.exe\" \"C:\path\ke\shopee-ads-autopilot\scripts\run_engine_once.py\"" ^
  /sc minute /mo 60
```

(`run_engine_once.py` sudah `chdir` ke folder aplikasi, jadi `.env` & database selalu ketemu.)

**Autostart saat Windows nyala:** letakkan shortcut `run.py` di folder
`shell:startup`, atau gunakan Task Scheduler trigger *At system startup*.

## 5. Menghubungkan toko nyata (mode LIVE)

1. Daftarkan app di [Shopee Open Platform](https://open.shopee.com) → dapatkan
   `partner_id` & `partner_key`. Scope **Ads (modul 117)** harus dimintakan ke
   **Shopee Partner Support** (tidak aktif default).
2. `copy .env.example .env` → isi `SHOPEE_PARTNER_ID`, `SHOPEE_PARTNER_KEY`,
   `SHOPEE_REDIRECT_URL` (harus sama persis dengan yang di App Console).
3. Otorisasi tiap toko/cabang:
   ```bat
   python scripts\authorize_shop.py --nama "Cabang Bandung"
   :: buka URL yang tercetak → login pemilik toko → Setujui → salin URL redirect
   python scripts\authorize_shop.py --nama "Cabang Bandung" --pasted-url "URL_HASIL"
   ```
   Token (±4 jam) di-refresh otomatis. Ulangi untuk semua cabang — >5 toko didukung.
4. Isi token & Chat ID **Telegram** di halaman Settings → kirim pesan uji.
5. Aktifkan **LIVE** di Settings (ada konfirmasi). Pantau Log Keputusan — aksi live pertama
   tetap tunduk pada dry-run 24 jam per aturan baru.

## 6. Endpoint API yang dipakai & tingkat verifikasinya

Proyek ini jujur soal kepastian API. Tiga tingkat:

- **Tingkat 1 — terkonfirmasi dari dokumentasi resmi open.shopee.com** (sudah dicek saat penulisan).
- **Tingkat 2 — butuh verifikasi saat akun developer aktif**: nama field persis di body/respons;
  ditandai `TODO-verifikasi` di kode. Mode LIVE jangan diaktifkan sebelum ini dicek.
- **Tingkat 3 — keputusan desain kami** (bukan klaim API).

| Modul / endpoint | Dipakai untuk | Tingkat |
|---|---|---|
| `POST /api/v2/auth/token/get`, `POST /api/v2/auth/access_token/get` | OAuth & refresh token (±4 jam) | 1 ✅ |
| Signing `partner_id+path+timestamp(+access_token+shop_id)` — HMAC-SHA256 partner_key | semua request | 1 ✅ |
| `GET /api/v2/ads/get_product_level_campaign_id_list` | daftar kampanye produk per toko | 1 ✅ |
| `GET /api/v2/ads/get_product_campaign_daily_performance` | performa harian kampanye (spend, GMV/direkomendasikan `broad_gmv`, impresi, klik, order) | 1 ✅ (nama field respons: **2** ⚠️) |
| `GET /api/v2/ads/get_all_cpc_ads_daily_performance` | alternatif monitoring lintas kampanye | 1 ✅ (belum dipakai engine) |
| `GET /api/v2/ads/get_total_balance` | sisa saldo iklan (rencana KPI dashboard) | 1 ✅ (belum dipakai) |
| `POST /api/v2/ads/edit_manual_product_ads` | ubah **budget & status** kampanye manual | **2** ⚠️ (nama field body: `TODO-verifikasi`) |
| `POST /api/v2/ads/edit_manual_product_ad_keywords` | penyesuaian **bid keyword** | **2** ⚠️ (eksekusi live sengaja ditahan sampai schema diverifikasi) |
| Famili GMS: `create/edit_gms_product_campaign`, `edit_gms_item_product_campaign`, `check_create_gms_product_campaign_eligibility` | aturan level kampanye & item GMV Max | **2** ⚠️ (sinkron data GMS: tahap berikutnya) |
| `create_auto_product_ads` / `edit_auto_product_ads` | ❌ **TIDAK dipakai** — ditandai Shopee *"coming offline soon"* | — |

Keputusan desain (Tingkat 3):

- Kampanye `auto` (Iklan Produk Otomatis): autopilot **menolak menulis** (endpoint deprecated) dan
  menyediakan aturan *notifikasi* untuk pengingat migrasi → manual ads `bidding_method=auto` + `roas_target`.
- Iklan Produk Otomatis di API memang **hanya bisa diubah budget & tanggal** (tanpa kontrol bid) —
  batasan produk Shopee, bukan batasan aplikasi ini.
- Interval scheduler, plafon, throttle, dry-run 24 jam: mekanisme keamanan rancangan kami.

## 7. Struktur kode

```
run.py                      server web + scheduler (utama)
scripts/
  seed_demo.py              data demo: 6 toko, kampanye manual/GMS/auto, performa 30 hari
  run_engine_once.py        satu siklus evaluasi (untuk Task Scheduler)
  authorize_shop.py         OAuth toko → token + pendaftaran ke dashboard
autopilot/
  web.py                    FastAPI + template (dashboard)
  engine.py                 rules engine: kondisi → guardrail → eksekusi
  executor.py               simulasi (demo) / preview (dry-run) / live (API)
  ads_source.py             sumber data: generator demo / tarik dari Shopee Ads API
  notify.py                 Telegram Bot API
  db.py + schema.sql        SQLite
shoppe_connector/           klien HTTP API v2 resmi (signing, retry, auto-refresh token)
tests/test_smoke.py         smoke test end-to-end (offline, tanpa API)
```

Menjalankan tes:

```bat
python -m pytest tests\ -v
```

## 8. FAQ singkat

- **Apakah ini aman untuk saldo saya?** Mode awal DEMO; aksi nyata hanya setelah LIVE, aturan
  lolos dry-run, dan selalu dibatasi plafon/lantai/throttle/kill-switch + log audit.
- **Kampanye saya tidak muncul?** Cek halaman Toko → catatan sinkron per toko; pastikan scope
  Ads aktif & token belum dicabut.
- **Telegram tidak terkirim?** Tes di Settings; cek token @BotFather & Chat ID @userinfobot.
- **Backup?** Cukup salin file `autopilot.db` (+ folder `tokens/` jika LIVE).

---

*Disclaimer: bukan produk resmi Shopee; gunakan sesuai Syarat & Ketentuan Shopee Open Platform.*
