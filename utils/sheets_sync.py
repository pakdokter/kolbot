"""
Sinkronisasi snapshot data KOL ke Google Sheets (read-mostly, untuk dilihat/diedit
visual oleh yang tidak pegang Telegram). Postgres tetap jadi sumber utama.

Dipanggil manual lewat command /sync_sheets. Bisa juga dijadwalkan lewat
Railway cron kalau mau otomatis berkala.
"""
import json
import logging

from config import GOOGLE_SHEETS_CREDENTIALS_JSON, GOOGLE_SHEETS_SPREADSHEET_ID
from config import STATUS_LABELS
import db

logger = logging.getLogger(__name__)

HEADER = [
    "kolaborasi_id", "kol_id", "nama", "tiktok_username", "ig_username",
    "followers_tiktok", "followers_ig", "niche", "domisili", "kontak",
    "tipe_kolaborasi", "preferensi_konten", "pic", "status",
    "tanggal_kunjungan", "link_konten", "tanggal_upload", "updated_at",
]


def is_configured() -> bool:
    return bool(GOOGLE_SHEETS_CREDENTIALS_JSON and GOOGLE_SHEETS_SPREADSHEET_ID)


async def sync_all():
    if not is_configured():
        raise RuntimeError(
            "Google Sheets belum dikonfigurasi. Set GOOGLE_SHEETS_CREDENTIALS_JSON "
            "dan GOOGLE_SHEETS_SPREADSHEET_ID di environment variable."
        )

    import gspread
    from google.oauth2.service_account import Credentials

    creds_dict = json.loads(GOOGLE_SHEETS_CREDENTIALS_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)

    sh = gc.open_by_key(GOOGLE_SHEETS_SPREADSHEET_ID)
    try:
        ws = sh.worksheet("KOL")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="KOL", rows=1000, cols=len(HEADER))

    rows = await db.list_all_kolaborasi()
    values = [HEADER]
    for r in rows:
        values.append([
            r["id"], r["kol_id"], r["nama"], r["tiktok_username"] or "", r["ig_username"] or "",
            r["followers_tiktok"] or "", r["followers_ig"] or "", "", "", "",
            r["tipe_kolaborasi"] or "", r["preferensi_konten"] or "", r["pic"] or "",
            STATUS_LABELS.get(r["status"], r["status"]),
            str(r["tanggal_kunjungan"] or ""), r["link_konten"] or "",
            str(r["tanggal_upload"] or ""), str(r["updated_at"]),
        ])

    ws.clear()
    ws.update(values)
    return len(rows)
