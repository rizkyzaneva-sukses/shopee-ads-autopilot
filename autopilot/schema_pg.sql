CREATE TABLE IF NOT EXISTS stores (
  id          SERIAL PRIMARY KEY,
  shop_id_ext TEXT UNIQUE,
  nama        TEXT NOT NULL,
  autopilot_on INTEGER NOT NULL DEFAULT 1,
  plafon_harian DOUBLE PRECISION NOT NULL DEFAULT 0,
  last_sync_at TEXT,
  created_at  TEXT NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS campaigns (
  id            SERIAL PRIMARY KEY,
  store_id      INTEGER NOT NULL REFERENCES stores(id),
  ext_id        TEXT NOT NULL,
  nama          TEXT NOT NULL,
  type          TEXT NOT NULL DEFAULT 'manual',
  bidding_method TEXT NOT NULL DEFAULT 'auto',
  status        TEXT NOT NULL DEFAULT 'ongoing',
  daily_budget  DOUBLE PRECISION NOT NULL DEFAULT 0,
  roas_target   DOUBLE PRECISION NOT NULL DEFAULT 0,
  start_date    TEXT, end_date TEXT,
  sinkron_terakhir TEXT,
  UNIQUE (store_id, ext_id)
);
CREATE INDEX IF NOT EXISTS idx_campaigns_store ON campaigns (store_id);

CREATE TABLE IF NOT EXISTS perf_daily (
  id         SERIAL PRIMARY KEY,
  campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  tanggal    TEXT NOT NULL,
  spend DOUBLE PRECISION NOT NULL DEFAULT 0, gmv DOUBLE PRECISION NOT NULL DEFAULT 0,
  impresi INTEGER NOT NULL DEFAULT 0, klik INTEGER NOT NULL DEFAULT 0,
  konversi DOUBLE PRECISION NOT NULL DEFAULT 0,
  UNIQUE (campaign_id, tanggal)
);
CREATE INDEX IF NOT EXISTS idx_perf ON perf_daily (campaign_id, tanggal);

CREATE TABLE IF NOT EXISTS rules (
  id           SERIAL PRIMARY KEY,
  nama         TEXT NOT NULL,
  enabled      INTEGER NOT NULL DEFAULT 1,
  priority     INTEGER NOT NULL DEFAULT 50,
  scope_type   TEXT NOT NULL DEFAULT 'all',
  scope_value  TEXT NOT NULL DEFAULT '',
  metric       TEXT NOT NULL,
  window_days  INTEGER NOT NULL DEFAULT 7,
  comparator   TEXT NOT NULL,
  threshold    DOUBLE PRECISION NOT NULL DEFAULT 0,
  cond2_metric TEXT NOT NULL DEFAULT '',
  cond2_comparator TEXT NOT NULL DEFAULT 'gte',
  cond2_threshold DOUBLE PRECISION NOT NULL DEFAULT 0,
  cond2_window INTEGER NOT NULL DEFAULT 7,
  action       TEXT NOT NULL,
  action_value DOUBLE PRECISION NOT NULL DEFAULT 20,
  budget_floor DOUBLE PRECISION NOT NULL DEFAULT 20000,
  budget_ceiling DOUBLE PRECISION NOT NULL DEFAULT 0,
  max_actions_day INTEGER NOT NULL DEFAULT 2,
  requires_confirm INTEGER NOT NULL DEFAULT 0,
  notify       TEXT NOT NULL DEFAULT 'telegram',
  dryrun_until TEXT NOT NULL DEFAULT '',
  created_at   TEXT NOT NULL DEFAULT NOW(),
  updated_at   TEXT
);

CREATE TABLE IF NOT EXISTS decisions (
  id          SERIAL PRIMARY KEY,
  created_at  TEXT NOT NULL DEFAULT NOW(),
  store_id    INTEGER, campaign_id INTEGER, rule_id INTEGER,
  mode        TEXT NOT NULL DEFAULT 'demo',
  kondisi     TEXT,
  nilai_metrik TEXT,
  aksi        TEXT, nilai_aksi TEXT,
  status      TEXT NOT NULL,
  detail      TEXT
);
CREATE INDEX IF NOT EXISTS idx_decisions ON decisions (created_at);

CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL DEFAULT ''
);
