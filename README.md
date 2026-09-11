# Bot Manajemen KOL Stoa Space

Bot Telegram untuk dokumentasi dan arsip KOL (TikTok/Instagram influencer) yang berkolaborasi
dengan Stoa Space, dari tahap approach sampai review performa konten.

## Setup

1. `python -m venv venv && source venv/bin/activate`
2. `pip install -r requirements.txt`
3. Copy `.env.example` ke `.env`, isi:
   - `TELEGRAM_BOT_TOKEN` dari @BotFather
   - `DATABASE_URL` Postgres (bisa Railway Postgres plugin)
   - `OPENAI_API_KEY` (opsional, untuk OCR screenshot profil — kosongkan kalau tidak dipakai)
   - `GOOGLE_SHEETS_CREDENTIALS_JSON` + `GOOGLE_SHEETS_SPREADSHEET_ID` (opsional, untuk sync ke Sheets)
4. Jalankan: `python bot.py` — skema database otomatis dibuat saat start pertama kali.

## Deploy ke Railway

1. Push repo ini ke GitHub, buat project baru di Railway, hubungkan repo.
2. Tambahkan Postgres plugin, Railway otomatis isi `DATABASE_URL`.
3. Set environment variable lain (`TELEGRAM_BOT_TOKEN`, dst) di Railway.
4. `Procfile` sudah diarahkan ke `worker: python bot.py`.

## Alur Pemakaian

1. `/input_kol` — staff upload screenshot TikTok & IG (atau `/skip`), bot coba baca data via AI
   vision sebagai draft, lalu staff mengisi/konfirmasi tiap field. Simpan dengan `/simpan`.
2. Setelah tersimpan, kolaborasi mulai di status **Sudah Diapproach**. Update status pakai:
   - `/reply <id>` → Sudah Membalas
   - `/jadwal <id> <YYYY-MM-DD>` → Terjadwal
   - `/reschedule <id> <YYYY-MM-DD> [alasan]` → ubah jadwal
   - `/tolak <id> [alasan]` → Ditolak
   - `/batalkan <id> [alasan]` → Batal
   - `/berkunjung <id>` → Sudah Berkunjung
   - `/upload <id> <link>` → Konten Sudah Upload
   - `/performa <id> <views> <likes> <comments> [shares] [saves]` → Performa Direview
3. Feedback pasca kunjungan: `/feedback <id> <teks>`, lihat dengan `/lihat_feedback <id>`.
4. Lihat daftar: `/list_kol`, `/belum_membalas`, `/sudah_membalas`, `/terjadwal`,
   `/sudah_berkunjung`, `/sudah_upload`, `/tolak_batal`, `/detail_kol <username>`.
5. `/sync_sheets` untuk push snapshot terbaru ke Google Sheets (kalau sudah dikonfigurasi).

`<id>` di semua command status/performa/feedback adalah **kolaborasi_id**, bukan kol_id — satu KOL
bisa punya banyak kolaborasi (repeat collab), tiap kolaborasi jalan sendiri di pipeline status.

## Struktur

- `schema.sql` — skema tabel Postgres
- `db.py` — semua query database (asyncpg)
- `config.py` — env vars, label status, aturan transisi status
- `handlers/input_kol.py` — conversation input KOL baru + screenshot OCR
- `handlers/status.py` — command update status pipeline
- `handlers/lists.py` — command daftar/list dan detail KOL
- `handlers/performa_feedback.py` — input & lihat performa konten + feedback
- `utils/vision.py` — ekstraksi draft data dari screenshot (OpenAI vision, opsional)
- `utils/sheets_sync.py` — sinkronisasi snapshot ke Google Sheets (opsional)

## Belum termasuk di v1 ini (bisa ditambah kalau perlu)

- Role/permission staff (saat ini semua yang bisa akses bot boleh input dan lihat semua data)
- Reminder otomatis untuk KOL yang lama tidak membalas (sudah dikonfirmasi tidak perlu)
- Edit data KOL/kolaborasi setelah tersimpan (saat ini hanya bisa update status, bukan edit field)
