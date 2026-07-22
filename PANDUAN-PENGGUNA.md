# 📖 Panduan Pengguna — Shopee Ads Autopilot

> **Versi 1.0** · Terakhir diperbarui: Juli 2026

---

## Daftar Isi

1. [Apa itu Shopee Ads Autopilot?](#1-apa-itu-shopee-ads-autopilot)
2. [Instalasi & Quick Start (Mode DEMO)](#2-instalasi--quick-start-mode-demo)
3. [Tur Setiap Halaman Dashboard](#3-tur-setiap-halaman-dashboard)
4. [Cara Membuat Aturan Step-by-Step](#4-cara-membuat-aturan-step-by-step)
5. [Panduan Mengisi Prioritas](#5-panduan-mengisi-prioritas)
6. [Membaca Log Keputusan](#6-membaca-log-keputusan)
7. [Setup Telegram & Kirim Pesan Uji](#7-setup-telegram--kirim-pesan-uji)
8. [Menjalankan 24 Jam di PC Windows](#8-menjalankan-24-jam-di-pc-windows)
9. [Roadmap dari DEMO ke LIVE](#9-roadmap-dari-demo-ke-live)
10. [Jujur soal API](#10-jujur-soal-api)
11. [Troubleshooting & FAQ](#11-troubleshooting--faq)
12. [Glosarium Iklan untuk Pemula](#12-glosarium-iklan-untuk-pemula)

---

## 1. Apa itu Shopee Ads Autopilot?

**Shopee Ads Autopilot** adalah aplikasi internal untuk mengotomatiskan pengelolaan iklan Shopee di banyak toko/cabang. Aplikasi ini berjalan di PC Windows Anda sendiri — bukan layanan cloud, bukan SaaS berlangganan.

**Untuk siapa aplikasi ini?**

- **Pemilik toko Shopee multi-cabang** yang ingin iklannya dikelola otomatis (naikkan budget kalau untung, turunkan/pause kalau boncos).
- **Manajer iklan** yang perlu melihat performa semua cabang dalam satu dashboard.
- **Siapa saja** yang ingin belajar mengelola iklan Shopee dengan aman — karena mode pertama kali adalah **DEMO** (simulasi, saldo iklan 100% aman).

**Yang perlu Anda tahu sebelum mulai:**

| Hal | Keterangan |
|-----|-----------|
| **Mode awal** | DEMO — semua aksi hanya simulasi di database lokal, **tidak ada panggilan API ke Shopee** |
| **Database** | SQLite lokal (`autopilot.db`), cukup satu file untuk backup |
| **Port default** | `http://127.0.0.1:8765` (buka di browser) |
| **Toko didukung** | >5 cabang dalam satu dashboard |
| **Bahasa antarmuka** | Bahasa Indonesia |

---

## 2. Instalasi & Quick Start (Mode DEMO)

Anda hanya butuh **Python 3.10+** yang terinstall di Windows. Tidak perlu Docker, Node.js, atau tools tambahan.

### Langkah 1 — Install Python

Jika belum punya Python, download dari [python.org](https://www.python.org/downloads/) dan centang **"Add Python to PATH"** saat instalasi.

### Langkah 2 — Install dependensi

Buka **PowerShell** atau **Command Prompt**, lalu jalankan:

```bat
cd folder-aplikasi
python -m pip install -r requirements.txt
```

Contoh:

```bat
cd C:\Users\Anda\Downloads\shopee-ads-autopilot
python -m pip install -r requirements.txt
```

### Langkah 3 — Isi data demo

Perintah ini membuat 6 toko cabang, 30 kampanye (semua tipe: manual, GMS, auto), dan 30 hari data performa simulasi:

```bat
python scripts\seed_demo.py
```

Anda akan melihat output seperti:

```
✅ 6 toko, 30 kampanye, performa 30 hari ke belakang dibuat.
✅ 4 aturan contoh ditambahkan (otomatis dry-run 24 jam pertama).
▶ Siklus evaluasi pertama: {'evaluasi': 84, 'terpicu': 17, ...}
```

### Langkah 4 — Jalankan server

```bat
python run.py
```

Anda akan melihat:

```
================================================================
  🚀 Shopee Ads Autopilot
  Dashboard : http://127.0.0.1:8765
  Mode awal : DEMO  (kill-switch di pojok kanan atas)
================================================================
```

### Langkah 5 — Buka dashboard

Buka browser dan kunjungi:

```
http://127.0.0.1:8765
```

Dashboard akan menampilkan 6 toko, 30 kampanye, dan data performa demo.

> **Untuk menjalankan ulang demo dari nol:**
> ```bat
> python scripts\seed_demo.py --reset
> ```

> **Opsi tambahan:**
> ```bat
> python run.py --port 9000        # ganti port
> python run.py --no-scheduler     # matikan scheduler otomatis
> ```

---

## 3. Tur Setiap Halaman Dashboard

Dashboard terdiri dari 6 halaman utama. Akses semua halaman dari **menu navigasi** di bagian atas.

### 3.1 Monitoring (`http://127.0.0.1:8765/`)

**Fungsi:** Halaman utama — menampilkan ringkasan kesehatan iklan semua toko dalam satu pandangan.

**Yang ditampilkan:**

| Elemen | Keterangan |
|--------|-----------|
| **KPI 4 kotak** | Spend 7 Hari, GMV 7 Hari, ROAS 7 Hari (hijau jika ≥2, merah jika <2), Jumlah Kampanye Aktif |
| **Tabel Kampanye** | Daftar semua kampanye dengan kolom: Toko, Nama, Tipe (MANUAL/GMS/AUTO), Status (ongoing/paused), Budget/hari, Spend 7h, GMV 7h, ROAS 7h, ROAS Target |
| **Tren 14 Hari** | Grafik SVG garis Spend vs GMV — biru untuk GMV, kuning untuk Spend |
| **Keputusan Terakhir** | 8 entri terakhir dari Log Keputusan |

**Tombol penting:**

| Tombol | Fungsi |
|--------|--------|
| **Filter** | Dropdown "Semua toko" → pilih toko tertentu untuk memfilter tampilan |
| **▶ Jalankan Siklus Evaluasi Sekarang** | Jalankan satu siklus evaluasi aturan manual dari browser |

[screenshot: halaman Monitoring dengan KPI, tabel kampanye, dan grafik tren]

### 3.2 Aturan (`http://127.0.0.1:8765/rules`)

**Fungsi:** Tempat Anda membuat, mengedit, dan mengelola aturan otomatis (rules) autopilot.

**Yang ditampilkan:**

| Elemen | Keterangan |
|--------|-----------|
| **Tabel Aturan** | Daftar semua aturan: tombol ON/OFF, Nama, Prioritas, Scope, Kondisi, Aksi, Batas Aman, Dry-run s/d tanggal |
| **Form Aturan** | Di bawah tabel — form untuk tambah baru atau edit aturan yang dipilih |

**Tombol penting:**

| Tombol | Fungsi |
|--------|--------|
| **ON / OFF** | Toggle aktif/nonaktif aturan (tidak menghapus, hanya menonaktifkan) |
| **ubah** | Edit aturan yang sudah ada |
| **hapus** | Hapus aturan permanen (konfirmasi dulu) |
| **▶ Jalankan Evaluasi Sekarang** | Jalankan siklus evaluasi langsung dari halaman Aturan |

**Kolom tabel yang perlu dipahami:**

- **Scope:** Siapa yang kena aturan — "Semua kampanye", "Toko #X", "Kampanye #X", atau "Tipe MANUAL/GMS/AUTO"
- **Kondisi:** Metrik yang dicek + pembanding + ambang + jendela hari. Contoh: `roas < 1.0 (7h) DAN spend ≥ 100000 (7h)`
- **Aksi:** Yang akan dilakukan jika kondisi terpenuhi — naikkan/turunkan budget, pause, resume, bid up/down, atau cuma notifikasi
- **Batas aman:** Lantai budget (budget tidak boleh di bawah ini), plafon per kampanye (tidak boleh lebih dari ini), maks aksi per hari
- **Dry-run s/d:** Aturan baru otomatis dry-run (hanya dicatat, belum eksekusi) sampai tanggal ini

[screenshot: halaman Aturan dengan tabel dan form]

### 3.3 Log Keputusan (`http://127.0.0.1:8765/log`)

**Fungsi:** Jejak audit semua keputusan autopilot. Setiap kali aturan dievaluasi dan menghasilkan aksi, semuanya tercatat di sini permanen.

**Kolom tabel:**

| Kolom | Keterangan |
|-------|-----------|
| **Waktu** | Kapan keputusan dibuat |
| **Toko** | Nama toko cabang |
| **Kampanye** | Nama kampanye yang terdampak |
| **Aturan** | Nama aturan yang memicu |
| **Kondisi/Metrik** | Ringkasan kondisi yang terpenuhi + snapshot metrik |
| **Aksi** | Aksi yang diambil + nilai |
| **Mode** | demo / dryrun / live |
| **Status** | executed / dryrun / throttled / blocked / pending / rejected |
| **Konfirmasi** | Tombol ✔ setujui dan ✖ tolak (hanya muncul untuk status pending) |

**Tombol penting:**

| Tombol | Fungsi |
|--------|--------|
| **Filter status** | Dropdown untuk menampilkan hanya status tertentu (pending, executed, dll.) |
| **Filter toko** | Dropdown untuk memfilter per toko |
| **✔ setujui** | Setujui aksi yang menunggu konfirmasi (hanya untuk status `pending`) |
| **✖** | Tolak aksi yang menunggu konfirmasi |

[screenshot: halaman Log Keputusan dengan tabel]

### 3.4 Kampanye (`http://127.0.0.1:8765/kampanye`)

**Fungsi:** Daftar lengkap semua kampanye iklan yang dipantau autopilot — semua toko, semua jenis.

**Kolom tabel:**

| Kolom | Keterangan |
|-------|-----------|
| **Toko** | Nama cabang |
| **Kampanye** | Nama kampanye + ext_id (ID eksternal) |
| **Tipe** | MANUAL (iklan produk individual), GMS (GMV Max / iklan grup), AUTO (iklan produk otomatis) |
| **Bidding** | auto atau manual |
| **Status** | ongoing (aktif), paused (jeda), ended (selesai) |
| **Budget/hari** | Budget harian kampanye (∞ jika unlimited) |
| **ROAS target** | Target ROAS untuk kampanye GMS |
| **Spend 7h / GMV 7h / ROAS 7h** | Performa 7 hari terakhir |

**Tombol penting:**

| Tombol | Fungsi |
|--------|--------|
| **Filter** | Dropdown untuk memfilter berdasarkan Toko, Tipe, atau Status |
| **↻ Sinkron + Evaluasi** | Tarik data terbaru dari API (mode LIVE) atau generate data demo baru + jalankan evaluasi |

> ⚠️ Tag `[baik]` dan `[boros]` pada nama kampanye hanya penanda **data demo** — mereka menandakan kampanye mana yang akan berperforma "baik" (ROAS tinggi) atau "boros" (ROAS rendah) dalam simulasi.

[screenshot: halaman Kampanye dengan tabel]

### 3.5 Toko (`http://127.0.0.1:8765/toko`)

**Fungsi:** Kelola semua toko/cabang — tambah toko baru, atur plafon harian, dan aktifkan/nonaktifkan autopilot per toko.

**Kolom tabel:**

| Kolom | Keterangan |
|-------|-----------|
| **Nama** | Nama toko/cabang |
| **Shop ID** | ID Shopee (atau id internal untuk demo) |
| **Kampanye** | Jumlah kampanye di toko ini |
| **Budget aktif/hari** | Total budget semua kampanye ongoing |
| **Spend 7h / GMV 7h / ROAS 7h** | Agregat performa toko |
| **Autopilot** | ON/OFF — checkbox untuk mengaktifkan/mematikan autopilot di toko ini |
| **Sinkron terakhir** | Kapan terakhir kali data disinkronkan |
| **Plafon & izin** | Input plafon harian + checkbox autopilot + tombol simpan |

**Bagian bawah halaman:**

- **＋ Tambah toko manual:** Form untuk menambah toko baru (Shop ID opsional untuk demo)
- **🔐 Menghubungkan toko nyata:** Panduan singkat otorisasi OAuth Shopee

> 🛡️ **Plafon harian** adalah rem terakhir: total budget kampanye ongoing sebuah toko tidak akan pernah dinaikkan autopilot melebihi plafon ini — walau aturan menyuruh naik.

[screenshot: halaman Toko dengan tabel dan form]

### 3.6 Settings (`http://127.0.0.1:8765/settings`)

**Fungsi:** Mode operasi, interval scheduler, kredensial API, dan konfigurasi Telegram.

**Bagian yang tersedia:**

| Bagian | Keterangan |
|--------|-----------|
| **Mode operasi** | Tombol untuk beralih antara DEMO ↔ LIVE (LIVE membutuhkan konfirmasi) |
| **Interval siklus otomatis** | Input angka menit (min 5, max 720) — berapa sering scheduler menjalankan evaluasi |
| **Status kredensial API** | Hijau jika `SHOPEE_PARTNER_ID/KEY` sudah terisi, merah jika belum |
| **Telegram Bot Token** | Token dari @BotFather |
| **Telegram Chat ID** | Chat ID Anda dari @userinfobot |
| **💾 Simpan settings** | Simpan semua pengaturan di atas |
| **✈️ Kirim pesan uji Telegram** | Kirim pesan uji untuk memverifikasi konfigurasi Telegram |
| **Cara membuat bot Telegram** | Panduan langkah demi langkah (2 menit, gratis) |
| **Penjadwal di PC Windows** | Info tentang scheduler bawaan `run.py` dan alternatif Windows Task Scheduler |

[screenshot: halaman Settings]

---

## 4. Cara Membuat Aturan Step-by-Step

### Langkah 1 — Buka halaman Aturan

Klik menu **Aturan** di navigasi atas.

### Langkah 2 — Isi form di bawah tabel

Form terbagi menjadi beberapa bagian:

#### 4a. Informasi Dasar

| Field | Keterangan | Contoh |
|-------|-----------|--------|
| **Nama aturan** | Nama yang mudah diingat | "Rem kampanye boncos" |
| **Berlaku untuk (scope)** | Siapa yang kena aturan | "Semua kampanye", "Toko tertentu", "Kampanye tertentu", atau "Hanya tipe tertentu" (manual/gms/auto) |
| **Pilih** | Muncul jika scope bukan "Semua" — pilih toko/kampanye/tipe spesifik | Cabang Bandung, dll. |
| **Prioritas** | Angka kecil = dievaluasi duluan. Lihat [Panduan Prioritas](#5-panduan-mengisi-prioritas) | 10 |

#### 4b. Kondisi Utama

| Field | Keterangan | Contoh |
|-------|-----------|--------|
| **Metrik** | Apa yang diukur: ROAS, Spend, GMV, CTR, Konversi, Biaya/konversi | ROAS |
| **Jendela (hari)** | Periode pengukuran: 1, 3, 7, 14, atau 30 hari | 7 |
| **Pembanding** | `<` (kurang dari), `>` (lebih dari), `≥`, `≤`, "turun > X% vs periode sebelumnya", "naik > X% vs periode sebelumnya" | `<` |
| **Nilai ambang** | Angka ambang yang dibandingkan | 2 |

#### 4c. Kondisi ke-2 (Opsional, AND)

| Field | Keterangan | Contoh |
|-------|-----------|--------|
| **Kondisi ke-2** | Pilih metrik tambahan, atau "— tidak ada —" jika tidak perlu | Spend |
| **Pembanding ke-2** | Pembanding untuk kondisi ke-2 | `≥` |
| **Ambang ke-2** | Angka ambang ke-2 | 100000 |
| **Jendela ke-2** | Periode untuk kondisi ke-2 | 7 |

#### 4d. Aksi

| Field | Keterangan | Contoh |
|-------|-----------|--------|
| **Aksi** | Apa yang dilakukan: Naikkan budget, Turunkan budget, Pause, Resume, Naikkan bid, Turunkan bid, Notifikasi saja | Turunkan budget |
| **Besar aksi (%)** | Persentase perubahan (untuk budget/bid) | 20 |

#### 4e. Batas Aman

| Field | Keterangan | Contoh |
|-------|-----------|--------|
| **Lantai budget (Rp)** | Budget tidak boleh turun di bawah ini | 20000 |
| **Plafon budget per kampanye (Rp)** | Budget tidak boleh naik di atas ini (0 = tanpa batas) | 500000 |
| **Maks aksi/hari per kampanye** | Anti-oscilasi — berapa kali aturan boleh dieksekusi per hari per kampanye | 2 |

#### 4f. Opsi Tambahan

| Field | Keterangan |
|-------|-----------|
| **Notifikasi** | Telegram atau Diam saja |
| **Persetujuan** | Centang "Minta konfirmasi dulu" jika aksi harus disetujui manual di Log Keputusan |

### Langkah 3 — Klik Simpan

Klik tombol **＋ Simpan aturan (dry-run 24 jam)**.

> ⚠️ **Aturan baru otomatis dry-run 24 jam pertama** — aturan akan dievaluasi dan hasilnya dicatat di Log, tapi **belum dieksekusi**. Ini untuk keamanan. Anda bisa mengakhiri dry-run lebih awal dari form edit.

### 5 Contoh Resep Aturan Siap Pakai

| Nama | Scope | Kondisi | Aksi | Batas Aman | Prioritas | Kapan Dipakai |
|------|-------|---------|------|-----------|-----------|---------------|
| **Rem kampanye boncos** | Semua kampanye | ROAS 7h < 1 **DAN** spend 7h ≥ Rp100rb | Budget −30% | Lantai Rp20rb, 1×/hari | 10 | Kampanye boros perlu ditekan budgetnya |
| **Gas kampanye juara** | Tipe MANUAL | ROAS 7h ≥ 3 | Budget +20% | Plafon Rp500rb/kampanye, 1×/hari | 20 | Kampanye bagus perlu dinaikkan budgetnya untuk scale up |
| **Pause total boncos** | Semua kampanye | ROAS 14h < 0.5 | ⏸ Pause | Minta konfirmasi, 1×/hari | 5 | Kampanye sangat merugi — pause total untuk evaluasi manual |
| **Pengingat migrasi** | Tipe AUTO | Spend iklan otomatis 7h > Rp50rb | 🔔 Notifikasi saja | 1×/hari | 90 | Pengingat bahwa kampanye auto perlu dimigrasi ke manual |
| **ROAS turun tajam** | Semua kampanye | ROAS turun > 30% vs 7 hari sebelumnya | Budget −20% | Lantai Rp30rb, 2×/hari | 15 | Mendeteksi penurunan performa mendadak |

---

## 5. Panduan Mengisi Prioritas

Prioritas menentukan **urutan evaluasi** aturan. Angka kecil = dievaluasi duluan.

| Jenis aturan | Isi prioritas | Contoh Anda |
|---|---|---|
| ⏸ Pause kampanye (paling tegas) | 5 | Pause total boncos → 5 ✓ |
| 📉 Turunkan budget / rem boncos | 10 | Rem kampanye boncos → 10 ✓ |
| 📈 Naikkan budget / gas juara | 20–30 | Gas kampanye juara → 20 ✓ |
| 🔔 Cuma notifikasi / pengingat | 90 | Pengingat migrasi → 90 ✓ |
| ❓ Tidak tahu / aturan umum | 50 | default |

**Kenapa aturan "rem/pengaman" harus berangka lebih kecil dari aturan "gas"?**

Karena aturan dievaluasi sesuai urutan prioritas — aturan dengan angka kecil dievaluasi duluan. Jika sebuah kampanye memenuhi syarat untuk *pause* (angka prioritas 5) dan sekaligus syarat untuk *naikkan budget* (angka prioritas 20), maka aturan pause akan dieksekusi terlebih dahulu. Ini memastikan bahwa **rem darurat selalu lebih cepat dari akselerasi** — budget tidak akan dinaikkan untuk kampanye yang seharunya dipause. Kebalikannya berbahaya: jika aturan "gas" (angka 20) dievaluasi duluan, budget bisa dinaikkan sejenak sebelum pause mengejar, yang berarti uang terbuang di kampanye yang akan dipause anyway.

> 💡 **Tips:** Mulai dengan angka yang "longgar" (misal pause=5, rem=10, gas=20, notif=90). Anda bisa menyesuaikan nanti berdasarkan hasil di Log Keputusan.

---

## 6. Membaca Log Keputusan

### Status dalam Log

| Status | Artinya |
|--------|---------|
| **executed** | ✅ Aksi berhasil dieksekusi (di mode DEMO = simulasi DB; di mode LIVE = via API) |
| **dryrun** | ⏳ Aksi hanya dicatat, belum dieksekusi (aturan masih dalam masa dry-run 24 jam) |
| **throttled** | 🚫 Aksi dibatasi karena sudah mencapai maks aksi/hari untuk kampanye ini |
| **blocked** | 🛑 Aksi dibatasi oleh pengaman — misal: budget unlimited, plafon toko tercapai, bidding bukan manual, atau kampanye auto |
| **pending** | ⏸ Aksi menunggu persetujuan Anda (minta konfirmasi) — buka Log, klik ✔ atau ✖ |
| **rejected** | ❌ Aksi ditolak oleh Anda dari halaman Log |

### Membaca Ringkasan Siklus

Setelah menjalankan siklus evaluasi, Anda akan melihat ringkasan seperti:

```
evaluasi 114, terpicu 23, eksekusi 3, dryrun 2, throttle 14, blocked 6, pending 2
```

**Apa artinya:**

| Komponen | Angka | Penjelasan |
|----------|-------|-----------|
| **evaluasi** | 114 | Jumlah total kombinasi aturan × kampanye yang dicek |
| **terpicu** | 23 | Kombinasi yang kondisinya terpenuhi (lolos filter kondisi) |
| **eksekusi** | 3 | Aksi yang benar-benar dijalankan |
| **dryrun** | 2 | Aksi yang hanya dicatat (aturan masih dry-run) |
| **throttle** | 14 | Aksi yang dibatasi karena sudah mencapai maks aksi/hari |
| **blocked** | 6 | Aksi yang dibatasi oleh pengaman (lantai/plafon/plafon toko/bukan manual/dll.) |
| **pending** | 2 | Aksi yang menunggu persetujuan Anda |

> 💡 **Tips:** Jika angka `throttle` tinggi, pertimbangkan untuk menaikkan `max_actions_day` pada aturan terkait. Jika angka `blocked` tinggi, periksa apakah lantai/plafon budget sudah sesuai.

---

## 7. Setup Telegram & Kirim Pesan Uji

### Langkah 1 — Buat Bot Telegram

1. Buka Telegram, cari chat **@BotFather**
2. Kirim `/newbot`
3. Ikuti instruksi: beri nama bot (misal: "Ads Autopilot") dan username (misal: `my_ads_bot`)
4. Salin **token** yang diberikan (format: `123456:AA...`)

### Langkah 2 — Dapatkan Chat ID

1. Kirim pesan apa saja ke bot baru Anda
2. Buka Telegram, cari chat **@userinfobot**
3. Kirim `/start` — bot akan menampilkan **Chat ID** Anda (angka seperti `123456789`)

### Langkah 3 — Isi di Settings

1. Buka halaman **Settings** di dashboard
2. Isi **Telegram Bot Token** dengan token dari @BotFather
3. Isi **Telegram Chat ID** dengan angka dari @userinfobot
4. Klik **💾 Simpan settings**

### Langkah 4 — Kirim Pesan Uji

Klik tombol **✈️ Kirim pesan uji Telegram**. Anda akan menerima pesan seperti:

```
✅ Uji Telegram dari Ads Autopilot berhasil!
```

Jika gagal, periksa:
- Token dan Chat ID sudah benar
- Bot sudah pernah dikirim pesan minimal sekali
- Koneksi internet aktif

> 💡 Setiap aksi autopilot (pause, naikkan budget, dll.) akan otomatis dikirim ke chat Telegram Anda.

---

## 8. Menjalankan 24 Jam di PC Windows

### Cara Utama: Server + Scheduler Bawaan

Jalankan perintah berikut dan **biarkan window tetap terbuka**:

```bat
python run.py
```

Scheduler thread bawaan akan menjalankan siklus evaluasi otomatis tiap interval (default 60 menit, bisa diubah di Settings). Interval dibaca ulang tiap putaran — perubahan di Settings langsung berlaku.

### Alternatif: Windows Task Scheduler

Jika Anda tidak ingin server web menyala terus, gunakan **Task Scheduler** bawaan Windows:

```bat
schtasks /create /tn "ShopeeAdsAutopilot" ^
  /tr "\"C:\path\ke\python.exe\" \"C:\path\ke\shopee-ads-autopilot\scripts\run_engine_once.py\"" ^
  /sc minute /mo 60
```

> Sesuaikan path python dan folder aplikasi Anda.

### Autostart saat Windows Nyala

Pilih salah satu:

- **Cara 1:** Buat shortcut `run.py` → taruh di folder `shell:startup`
- **Cara 2:** Gunakan Task Scheduler dengan trigger **At system startup**

### Backup

Database tersimpan dalam satu file: **`autopilot.db`** di folder aplikasi.

Untuk backup, cukup **salin file `autopilot.db`** ke lokasi aman.

Jika mode LIVE aktif, juga backup folder **`tokens/`** (berisi token OAuth per toko).

---

## 9. Roadmap dari DEMO ke LIVE

🗺️ **Roadmap Anda setelah ini**

### Minggu ini (main di Mode DEMO — tanpa risiko apa pun):

1. Jalankan 3 perintah di atas → dashboard terbuka dengan 6 toko + 30 kampanye contoh
2. Coba buat aturan sendiri di halaman Aturan (mis. "ROAS < 2 → turunkan budget 20%")
3. Klik ▶ Jalankan Siklus Evaluasi di Monitoring → lihat hasilnya di Log Keputusan
4. Isi Telegram di Settings (@BotFather → token, @userinfobot → chat ID) → "Kirim pesan uji"
5. Coba pencet ⛔ KILL-SWITCH di pojok kanan atas — rasakan rem daruratnya

### Nanti (menuju data toko asli Anda):

6. Daftarkan app di Shopee Open Platform → dapat `partner_id` + `partner_key` → isi ke file `.env`
7. Email/chat Shopee Partner Support minta scope Ads (modul 117) diaktifkan
8. Otorisasi tiap cabang: `python scripts\authorize_shop.py --nama "Cabang Bandung"`
9. Verifikasi field Tingkat 2 — bilang ke asisten AI saat sampai tahap ini
10. Baru aktifkan mode LIVE (aturan baru tetap otomatis dry-run 24 jam dulu)

---

## 10. Jujur soal API

Shopee Ads Autopilot menggunakan **Shopee Open Platform API v2 resmi**. Kami jujur soal seberapa siap setiap endpoint. Ada 3 tingkat verifikasi:

### Tingkat 1 — Terkonfirmasi dari Dokumentasi Resmi

Endpoint-endpoint ini sudah dikonfirmasi ada di [open.shopee.com](https://open.shopee.com):

| Endpoint | Kegunaan |
|----------|---------|
| `POST /api/v2/auth/token/get` | OAuth & refresh token (±4 jam) |
| `GET /api/v2/ads/get_product_level_campaign_id_list` | Daftar kampanye produk per toko |
| `GET /api/v2/ads/get_product_campaign_daily_performance` | Performa harian kampanye |
| `GET /api/v2/ads/get_total_balance` | Sisa saldo iklan |

### Tingkat 2 — Perlu Verifikasi Saat Akun Developer Aktif

Endpoint ini ada, tapi **nama field di body/respons perlu dicocokkan** dengan dokumentasi yang sebenarnya saat akun developer Shopee Anda aktif. Di kode, endpoint ini ditandai `TODO-verifikasi`.

| Endpoint | Kegunaan | Catatan |
|----------|---------|---------|
| `POST /api/v2/ads/edit_manual_product_ads` | Ubah budget & status kampanye manual | Nama field body perlu diverifikasi |
| `POST /api/v2/ads/edit_manual_product_ad_keywords` | Penyesuaian bid keyword | Schema perlu diverifikasi |

> ⚠️ **Mode LIVE tidak boleh diaktifkan sebelum Tingkat 2 diverifikasi.** Ini demi keamanan saldo iklan Anda.

### Tingkat 3 — Keputusan Desain Keamanan Aplikasi

Beberapa keputusan adalah rancangan keamanan kami, bukan klaim API:

- Kampanye **tipe AUTO** (Iklan Produk Otomatis) **tidak ditulis** autopilot — endpoint `create/edit_auto_product_ads` sudah ditandai Shopee *"coming offline soon"*
- **DRY-RUN 24 jam** per aturan baru adalah mekanisme keamanan bawaan
- **Kill-switch global**, **plafon per toko**, **lantai/plafon per kampanye**, **maks aksi/hari**: semua fitur pengaman yang kami rancang

---

## 11. Troubleshooting & FAQ

### Q1: Server tidak mau nyala?

**Periksa:**

1. Pastikan Python sudah terinstall: ketik `python --version` di terminal
2. Pastikan dependensi sudah diinstall: `python -m pip install -r requirements.txt`
3. Pastikan Anda berada di folder yang benar sebelum menjalankan `python run.py`
4. Jika muncul error `ModuleNotFoundError`, jalankan ulang `pip install`

### Q2: Port 8765 sudah dipakai?

Gunakan port lain:

```bat
python run.py --port 9000
```

Atau ubah di file `.env`:

```
PORT=9000
```

### Q3: Kampanye tidak muncul di dashboard?

1. Jalankan `python scripts\seed_demo.py` untuk data demo
2. Jika mode LIVE, pastikan toko sudah diotorisasi (cek halaman Toko → catatan sinkron)
3. Pastikan scope Ads (modul 117) sudah aktif di akun Shopee Open Platform Anda
4. Klik **↻ Sinkron + Evaluasi** di halaman Kampanye

### Q4: Telegram tidak terkirim?

1. Pastikan bot sudah pernah dikirim pesan minimal sekali
2. Cek token dan Chat ID sudah benar di halaman Settings
3. Klik **✈️ Kirim pesan uji Telegram** untuk menguji
4. Jika masih gagal, periksa koneksi internet

### Q5: Throttle terus (aksi dibatasi)?

Artinya aturan sudah mencapai batas maks aksi/hari untuk kampanye tertentu. Solusi:

- Naikkan `max_actions_day` di form edit aturan (misal dari 1 ke 2 atau 3)
- Atau tunggu sampai hari berikutnya — counter aksi di-reset otomatis

### Q6: Cara reset demo dari nol?

```bat
python scripts\seed_demo.py --reset
```

Perintah ini menghapus database lama dan membuat ulang data demo.

### Q7: Cara backup data?

Cukup salin file `autopilot.db` ke lokasi aman.

Jika mode LIVE aktif, juga backup folder `tokens/` (berisi token OAuth per toko).

### Q8: Cara matikan autopilot untuk 1 toko saja?

Buka halaman **Toko** → centang/uncentang checkbox **autopilot** di baris toko yang dimaksud → klik tombol **💾**.

Toko dengan autopilot **OFF** tidak akan dieksekusi oleh aturan mana pun, meskipun aturan scope-nya "Semua kampanye".

### Q9: Bagaimana cara mengakhiri dry-run aturan lebih awal?

Buka halaman **Aturan** → klik **ubah** pada aturan yang dimaksud → centang **"Akhiri dry-run lebih awal"** → Simpan. Aturan akan langsung aktif penuh.

### Q10: Apakah aman untuk saldo iklan saya?

Ya. Berikut lapisan keamanan yang selalu aktif:

1. **Mode awal DEMO** — tidak ada panggilan API tulis
2. **Dry-run 24 jam** — aturan baru di mode LIVE tetap hanya dicatat dulu
3. **Kill-switch global** — hentikan SEMUA aksi dalam 1 klik
4. **Autopilot per toko** — bisa dimatikan per cabang
5. **Plafon harian per toko** — total budget tidak melebihi batas
6. **Lantai & plafon per kampanye** — budget dibatasi rentang tertentu
7. **Maks aksi/hari** — anti-oscilasi
8. **Minta konfirmasi** — aksi tereksekusi hanya setelah persetujuan Anda
9. **Log Keputusan permanen** — semua keputusan bisa diaudit

---

## 12. Glosarium Iklan untuk Pemula

Istilah-istilah yang sering muncul di dashboard dan aturan:

| Istilah | Arti | Contoh Penggunaan |
|---------|------|-------------------|
| **ROAS** | *Return on Ad Spend* — berapa rupiah GMV yang dihasilkan dari setiap rupiah spend iklan. ROAS 3× = dari spend Rp10.000, dapat GMV Rp30.000. | "ROAS 7 hari ini 2.5×" |
| **GMV** | *Gross Merchandise Value* — total nilai transaksi (harga barang × jumlah) yang dihasilkan dari iklan. | "GMV 7 hari: Rp 5.000.000" |
| **CTR** | *Click-Through Rate* — persentase orang yang melihat iklan (impresi) lalu mengklik. CTR 2% = dari 1000 tayangan, 20 kali diklik. | "CTR turun ke 0.8%" |
| **Spend** | Jumlah uang yang keluar untuk iklan dalam periode tertentu. | "Spend 7 hari: Rp 200.000" |
| **Konversi** | Jumlah pembelian/tindakan yang dihasilkan dari klik iklan. | "Konversi hari ini: 5 transaksi" |
| **Biaya/konversi** | Berapa rupiah yang dikeluarkan untuk mendapatkan 1 konversi. Biaya/konversi Rp20.000 = dari spend Rp100.000, dapat 5 pembelian. | "Biaya/konversi: Rp 40.000" |
| **Budget harian** | Batas maksimum uang yang dihabiskan per hari untuk satu kampanye iklan. | "Budget harian: Rp 100.000" |
| **Bidding manual** | Metode di mana Anda (atau autopilot) mengatur bid/penawaran per keyword secara manual. Bisa dikontrol sepenuhnya. | "Kampanye dengan bidding manual bisa diatur bid keyword-nya" |
| **Bidding auto** | Metode di mana Shopee yang mengatur bid otomatis. Anda hanya bisa mengatur budget, ROAS target, dan tanggal. | "Kampanye auto: kontrol terbatas pada budget & tanggal" |
| **GMS / GMV Max** | *GMV Max* — tipe kampanye iklan grup yang fokus memaksimalkan total nilai transaksi. Bisa diatur di level kampanye dan item. | "GMV Max - Produk Juara" |
| **Pause** | Menghentikan sementara kampanye iklan tanpa menghapusnya. Bisa diaktifkan kembali (resume). | "Kampanye boncos → pause" |
| **Resume** | Mengaktifkan kembali kampanye yang sebelumnya dipause. | "Kampanye sudah diperbaiki → resume" |
| **Kill-switch** | Tombol darurat global — menghentikan SEMUA aksi autopilot dalam 1 klik. | "Klik ⛔ KILL-SWITCH untuk hentikan semua" |
| **Plafon** | Batas atas — total budget tidak boleh melebihi angka ini. | "Plafon harian toko: Rp 500.000" |
| **Lantai** | Batas bawah — budget tidak boleh turun di bawah angka ini. | "Lantai budget kampanye: Rp 20.000" |
| **Dry-run** | Mode percobaan — aturan dievaluasi dan hasilnya dicatat, tapi **belum dieksekusi**. | "Aturan baru dry-run 24 jam dulu" |
| **Throttle** | Pembatasan jumlah aksi per hari per kampanye untuk mencegah perubahan terlalu sering. | "Aksi di-throttle karena sudah maks hari ini" |

---

> **Catatan:** Aplikasi ini bukan produk resmi Shopee. Gunakan sesuai Syarat & Ketentuan Shopee Open Platform. Semua aksi tulis hanya via API resmi, dan mode DEMO tidak menyentuh saldo iklan Anda sama sekali.
