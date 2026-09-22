-- Skema database bot manajemen KOL Stoa Space
-- Postgres

CREATE TABLE IF NOT EXISTS kol (
    id SERIAL PRIMARY KEY,
    nama TEXT NOT NULL,
    tiktok_username TEXT,
    ig_username TEXT,
    followers_tiktok INTEGER,
    followers_ig INTEGER,
    following_tiktok INTEGER,
    following_ig INTEGER,
    likes_tiktok INTEGER,      -- total likes yang tampil di profil TikTok
    likes_ig INTEGER,          -- opsional, IG biasanya tidak menampilkan total likes di profil
    niche TEXT,
    engagement_rate NUMERIC,
    domisili TEXT,
    demografi_audiens TEXT,
    kontak TEXT,
    catatan TEXT,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Satu KOL bisa punya banyak kolaborasi (repeat collab)
CREATE TABLE IF NOT EXISTS kolaborasi (
    id SERIAL PRIMARY KEY,
    kol_id INTEGER NOT NULL REFERENCES kol(id) ON DELETE CASCADE,
    tipe_kolaborasi TEXT,          -- barter / paid / lainnya (teks bebas)
    preferensi_konten TEXT,        -- reel, video review, story, dll
    pic TEXT,                      -- staff yang approach
    status TEXT NOT NULL DEFAULT 'approached',
        -- approached | ditolak | replied | scheduled | batal
        -- visited | content_uploaded | performance_reviewed
    tanggal_kunjungan DATE,
    link_konten TEXT,
    tanggal_upload DATE,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_kolaborasi_kol_id ON kolaborasi(kol_id);
CREATE INDEX IF NOT EXISTS idx_kolaborasi_status ON kolaborasi(status);

-- Log setiap perpindahan status, termasuk histori reschedule
CREATE TABLE IF NOT EXISTS status_history (
    id SERIAL PRIMARY KEY,
    kolaborasi_id INTEGER NOT NULL REFERENCES kolaborasi(id) ON DELETE CASCADE,
    status_lama TEXT,
    status_baru TEXT NOT NULL,
    catatan TEXT,               -- misal alasan reschedule/ditolak/batal
    changed_by BIGINT,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_status_history_kolaborasi_id ON status_history(kolaborasi_id);

-- Screenshot akun (tiktok/ig) dan screenshot lain sebagai lampiran
CREATE TABLE IF NOT EXISTS screenshot (
    id SERIAL PRIMARY KEY,
    kol_id INTEGER REFERENCES kol(id) ON DELETE CASCADE,
    kolaborasi_id INTEGER REFERENCES kolaborasi(id) ON DELETE CASCADE,
    jenis TEXT NOT NULL,         -- tiktok_profile | ig_profile | lainnya
    telegram_file_id TEXT NOT NULL,
    ocr_raw_text TEXT,           -- hasil mentah dari AI vision, untuk audit
    uploaded_by BIGINT,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Performa konten setelah upload (input manual)
CREATE TABLE IF NOT EXISTS performa (
    id SERIAL PRIMARY KEY,
    kolaborasi_id INTEGER NOT NULL REFERENCES kolaborasi(id) ON DELETE CASCADE,
    views BIGINT,
    likes BIGINT,
    comments BIGINT,
    shares BIGINT,
    saves BIGINT,
    catatan TEXT,
    input_by BIGINT,
    input_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Migrasi ringan untuk deployment lama yang tabelnya sudah ada duluan
-- (CREATE TABLE IF NOT EXISTS di atas tidak menambah kolom baru ke tabel yang sudah ada)
ALTER TABLE kol ADD COLUMN IF NOT EXISTS following_tiktok INTEGER;
ALTER TABLE kol ADD COLUMN IF NOT EXISTS following_ig INTEGER;
ALTER TABLE kol ADD COLUMN IF NOT EXISTS likes_tiktok INTEGER;
ALTER TABLE kol ADD COLUMN IF NOT EXISTS likes_ig INTEGER;

-- Feedback staff setelah KOL berkunjung
CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    kolaborasi_id INTEGER NOT NULL REFERENCES kolaborasi(id) ON DELETE CASCADE,
    feedback_text TEXT NOT NULL,
    input_by BIGINT,
    input_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
