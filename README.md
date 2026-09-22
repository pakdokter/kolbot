# Bot Manajemen KOL Stoa Space

Bot Telegram untuk dokumentasi dan arsip KOL (TikTok/Instagram influencer) yang berkolaborasi
dengan Stoa Space, dari tahap approach sampai review performa konten.

## Setup

1. `python -m venv venv && source venv/bin/activate`
2. `pip install -r requirements.txt`
3. Install binary Tesseract OCR di sistem (dipakai `pytesseract` untuk baca screenshot):
   - Debian/Ubuntu: `sudo apt-get install tesseract-ocr`
   - macOS: `brew install tesseract`
   - Kalau deploy pakai `Dockerfile` yang sudah disediakan, ini otomatis terpasang.
4. Copy `.env.example` ke `.env`, isi:
   - `TELEGRAM_BOT_TOKEN` dari @BotFather
   - `DATABASE_URL` Postgres (bisa Railway Postgres plugin)
   - `GOOGLE_SHEETS_CREDENTIALS_JSON` + `GOOGLE_SHEETS_SPREADSHEET_ID` (opsional, kalau kosong bot tetap jalan tanpa sync)
5. Jalankan: `python bot.py` — skema database otomatis dibuat saat start pertama kali.

## Deploy ke Railway

1. Push repo ini ke GitHub, buat project baru di Railway, hubungkan repo.
2. Railway otomatis pakai `Dockerfile` yang ada di root repo (bukan railpack/nixpacks) —
   ini penting supaya binary `tesseract-ocr` ikut terpasang di image, bukan cuma package Python-nya.
   Kalau Railway masih kebaca pakai builder lain, cek di Settings → Build bahwa
   "Builder" di-set ke **Dockerfile**.
3. Tambahkan Postgres plugin, Railway otomatis isi `DATABASE_URL`.
4. Set environment variable lain (`TELEGRAM_BOT_TOKEN`, `GOOGLE_SHEETS_CREDENTIALS_JSON`, dst) di Railway.

## Alur Pemakaian

1. `/input_kol` — staff upload screenshot TikTok & IG (atau `/skip`), bot coba baca username &
   followers dari screenshot pakai Tesseract OCR sebagai draft kasar (niche TIDAK ditebak otomatis,
   selalu diisi manual). Staff mengisi/mengoreksi tiap field, simpan dengan `/simpan`.
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
5. **Sync ke Google Sheets otomatis** — begitu `GOOGLE_SHEETS_CREDENTIALS_JSON` dan
   `GOOGLE_SHEETS_SPREADSHEET_ID` diisi, bot otomatis push snapshot terbaru ke sheet "KOL" setiap
   ada perubahan data (input KOL baru, update status, input performa). `/sync_sheets` tetap ada
   kalau sewaktu-waktu mau trigger sync ulang secara manual.

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
- `utils/vision.py` — ekstraksi draft username/followers dari screenshot (Tesseract OCR, lokal)
- `utils/sheets_sync.py` — sinkronisasi otomatis snapshot ke Google Sheets
- `Dockerfile` — image Python 3.13 + `tesseract-ocr`, dipakai Railway untuk build & deploy

## Belum termasuk di v1 ini (bisa ditambah kalau perlu)

- Role/permission staff (saat ini semua yang bisa akses bot boleh input dan lihat semua data)
- Reminder otomatis untuk KOL yang lama tidak membalas (sudah dikonfirmasi tidak perlu)
- Edit data KOL/kolaborasi setelah tersimpan (saat ini hanya bisa update status, bukan edit field)
