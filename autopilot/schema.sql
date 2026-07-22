CREATE TABLE IF NOT EXISTS stores (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  shop_id_ext TEXT UNIQUE,
  nama        TEXT NOT NULL,
  autopilot_on INTEGER NOT NULL DEFAULT 1,    -- autopilot boleh aksi di toko ini?
  plafon_harian REAL NOT NULL DEFAULT 0,      -- 0 = tanpa plafon; total budget harian semua kampanye toko ini
  last_sync_at TEXT,
  created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS campaigns (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  store_id      INTEGER NOT NULL REFERENCES stores(id),
  ext_id        TEXT NOT NULL,               -- campaign_id dari API (atau id demo)
  nama          TEXT NOT NULL,
  type          TEXT NOT NULL DEFAULT 'manual',   -- manual | gms | auto
  bidding_method TEXT NOT NULL DEFAULT 'auto',    -- auto | manual
  status        TEXT NOT NULL DEFAULT 'ongoing',  -- ongoing | paused | ended
  daily_budget  REAL NOT NULL DEFAULT 0,          -- 0 = unlimited
  roas_target   REAL NOT NULL DEFAULT 0,          -- 0 = nonaktif
  start_date    TEXT, end_date TEXT,
  sinkron_terakhir TEXT,
  UNIQUE (store_id, ext_id)
);
CREATE INDEX IF NOT EXISTS idx_campaigns_store ON campaigns (store_id);

CREATE TABLE IF NOT EXISTS perf_daily (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  tanggal    TEXT NOT NULL,                  -- YYYY-MM-DD
  spend REAL NOT NULL DEFAULT 0, gmv REAL NOT NULL DEFAULT 0,
  impresi INTEGER NOT NULL DEFAULT 0, klik INTEGER NOT NULL DEFAULT 0,
  konversi REAL NOT NULL DEFAULT 0,
  UNIQUE (campaign_id, tanggal)
);
CREATE INDEX IF NOT EXISTS idx_perf ON perf_daily (campaign_id, tanggal);

CREATE TABLE IF NOT EXISTS rules (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  nama         TEXT NOT NULL,
  enabled      INTEGER NOT NULL DEFAULT 1,
  priority     INTEGER NOT NULL DEFAULT 50,      -- angka kecil = dievaluasi duluan
  scope_type   TEXT NOT NULL DEFAULT 'all',      -- all | store | campaign | type
  scope_value  TEXT NOT NULL DEFAULT '',         -- id toko / id kampanye / manual|gms|auto
  -- kondisi utama
  metric       TEXT NOT NULL,                    -- roas|spend|gmv|ctr|konversi|biaya_konversi
  window_days  INTEGER NOT NULL DEFAULT 7,
  comparator   TEXT NOT NULL,                    -- lt|gt|gte|lte|drop|rise (drop/rise vs periode sebelumnya, %)
  threshold    REAL NOT NULL DEFAULT 0,
  -- kondisi ke-2 (opsional, selalu AND)
  cond2_metric TEXT NOT NULL DEFAULT '',
  cond2_comparator TEXT NOT NULL DEFAULT 'gte',
  cond2_threshold REAL NOT NULL DEFAULT 0,
  cond2_window INTEGER NOT NULL DEFAULT 7,
  -- aksi
  action       TEXT NOT NULL,                    -- budget_up|budget_down|pause|resume|bid_up|bid_down|notify
  action_value REAL NOT NULL DEFAULT 20,         -- persen (budget/bid) — diabaikan utk pause/resume/notify
  -- batas aman
  budget_floor REAL NOT NULL DEFAULT 20000,      -- lantai budget harian
  budget_ceiling REAL NOT NULL DEFAULT 0,        -- 0 = tanpa plafon per kampanye
  max_actions_day INTEGER NOT NULL DEFAULT 2,
  requires_confirm INTEGER NOT NULL DEFAULT 0,   -- 1 = minta persetujuan dulu
  notify       TEXT NOT NULL DEFAULT 'telegram', -- telegram|confirm|silent
  dryrun_until TEXT NOT NULL DEFAULT '',         -- aturan baru otomatis dry-run sampai ts ini
  created_at   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  updated_at   TEXT
);

CREATE TABLE IF NOT EXISTS decisions (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  store_id    INTEGER, campaign_id INTEGER, rule_id INTEGER,
  mode        TEXT NOT NULL DEFAULT 'demo',      -- demo|dryrun|live
  kondisi     TEXT,                              -- ringkasan kondisi yg terpenuhi
  nilai_metrik TEXT,                             -- snapshot metrik saat evaluasi
  aksi        TEXT, nilai_aksi TEXT,
  status      TEXT NOT NULL,                     -- executed|pending|dryrun|throttled|skipped|rejected|blocked
  detail      TEXT
);
CREATE INDEX IF NOT EXISTS idx_decisions ON decisions (created_at);

CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL DEFAULT ''
);
