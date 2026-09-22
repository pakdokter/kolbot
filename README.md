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

## Alur Pemakaian (flow berbasis tombol)

1. `/input_kol` — staff upload screenshot TikTok & IG (atau `/skip`). Bot baca **followers,
   following, dan likes** dari screenshot pakai Tesseract OCR sebagai draft kasar (niche TIDAK
   pernah ditebak otomatis, selalu diisi manual). Pertanyaannya dikelompokkan per bagian biar
   enak dibaca: 📋 Identitas & Platform → 📊 Statistik Akun → 🎯 Profil Audiens → 🤝 Kerja Sama.
   Simpan dengan `/simpan`.
2. Begitu tersimpan, bot **langsung lanjut** nampilin tombol: "Apakah KOL ini sudah membalas?"
   [✅ Sudah Membalas] [❌ Ditolak] [⏳ Belum Dibaca]. Staff tinggal tap, tidak perlu ingat/ketik
   command atau kolaborasi_id.
3. Alur tombolnya mengikuti status kolaborasi (kayak flowchart, satu jalur per waktu):
   - **Sudah Membalas** → bot minta tanggal jadwal kunjungan (ketik `YYYY-MM-DD`) → jadi **Terjadwal**
   - **Terjadwal** → tombol [🏠 Sudah Berkunjung] [🔁 Reschedule] [🚫 Batalkan]
   - **Sudah Berkunjung** → tombol [🎬 Konten Sudah Naik], lanjut ke alur upload konten:
     1. Kirim link konten
     2. Kirim screenshot Google Review (opsional, `/skip`)
     3. Kirim screenshot halaman konten (wajib) — bot baca angka-angka yang kebaca lewat OCR
        sebagai bantuan (angka mentah, tidak bisa dipastikan mana likes/komen/saves karena cuma
        nempel ikon tanpa label), staff ketik manual: `views likes comments shares saves`
        (shares/saves boleh `-`)
     4. Kirim screenshot komentar (opsional, `/skip`)
     5. Selesai — kolaborasi otomatis ditandai **Content Uploaded** lalu **Performance Reviewed**
   - Kalau kolaborasi ditinggal di tengah jalan (misal masih "Belum Dibaca" atau mau lanjut lagi
     nanti), buka ulang menunya dengan `/panel <kolaborasi_id>`.
4. Feedback pasca kunjungan (di luar alur tombol, opsional): `/feedback <id> <teks>`, lihat dengan
   `/lihat_feedback <id>`.
5. Lihat daftar: `/list_kol`, `/belum_membalas`, `/sudah_membalas`, `/terjadwal`,
   `/sudah_berkunjung`, `/sudah_upload`, `/tolak_batal`, `/detail_kol <username>`.
6. **Sync ke Google Sheets otomatis** — begitu `GOOGLE_SHEETS_CREDENTIALS_JSON` dan
   `GOOGLE_SHEETS_SPREADSHEET_ID` diisi, bot otomatis push snapshot terbaru ke sheet "KOL" setiap
   ada perubahan data. `/sync_sheets` tetap ada buat trigger sync ulang manual.

Command manual di `handlers/status.py` dan `handlers/performa_feedback.py`
(`/reply`, `/jadwal`, `/tolak`, `/berkunjung`, `/upload`, `/performa`, dst, semua pakai
`<kolaborasi_id>`) tetap tersedia sebagai jalur cadangan buat yang lebih suka ketik command
langsung daripada tap tombol — keduanya baca/tulis ke tabel yang sama jadi bisa dicampur bebas.

`<id>` di semua command manual adalah **kolaborasi_id**, bukan kol_id — satu KOL bisa punya
banyak kolaborasi (repeat collab), tiap kolaborasi jalan sendiri di pipeline status.

## Struktur

- `schema.sql` — skema tabel Postgres
- `db.py` — semua query database (asyncpg)
- `config.py` — env vars, label status, aturan transisi status
- `handlers/input_kol.py` — conversation input KOL baru (grouped UI) + screenshot OCR
- `handlers/flow.py` — panel status berbasis tombol (inline keyboard), pengganti utama command manual
- `handlers/konten.py` — conversation upload konten (link, Google review, halaman konten + OCR, komentar)
- `handlers/status.py` — command manual update status pipeline (cadangan)
- `handlers/lists.py` — command daftar/list dan detail KOL
- `handlers/performa_feedback.py` — command manual input/lihat performa + feedback (cadangan)
- `utils/vision.py` — ekstraksi draft dari screenshot (Tesseract OCR, lokal): username/followers/
  following/likes dari profil, dan daftar angka mentah dari screenshot konten
- `utils/sheets_sync.py` — sinkronisasi otomatis snapshot ke Google Sheets
- `Dockerfile` — image Python 3.13 + `tesseract-ocr`, dipakai Railway untuk build & deploy

## Belum termasuk di v1 ini (bisa ditambah kalau perlu)

- Role/permission staff (saat ini semua yang bisa akses bot boleh input dan lihat semua data)
- Reminder otomatis untuk KOL yang lama tidak membalas (sudah dikonfirmasi tidak perlu)
- Edit data KOL/kolaborasi setelah tersimpan (saat ini hanya bisa update status, bukan edit field)
- Deteksi otomatis likes/komen/saves per-field dari screenshot konten (ikon tanpa label bikin ini
  tidak reliable dari OCR murni) — saat ini cuma dikasih daftar angka bantuan, staff yang pasangkan
