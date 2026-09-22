import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]

# Ekstraksi data dari screenshot profil TikTok/Instagram pakai Tesseract OCR (lokal, gratis,
# tidak butuh API key). Niche/kategori selalu diisi manual, tidak ditebak otomatis.

# Google Sheets sync. Kosongkan untuk matikan (bot tetap jalan, cuma tanpa sync).
# Setiap ada perubahan data (input KOL baru, update status, performa) bot otomatis sync ke sini.
GOOGLE_SHEETS_CREDENTIALS_JSON = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_JSON", "")
GOOGLE_SHEETS_SPREADSHEET_ID = os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID", "")

STATUS_LABELS = {
    "approached": "Sudah Diapproach",
    "ditolak": "Ditolak / Not Interested",
    "replied": "Sudah Membalas",
    "scheduled": "Terjadwal",
    "batal": "Batal",
    "visited": "Sudah Berkunjung",
    "content_uploaded": "Konten Sudah Upload",
    "performance_reviewed": "Performa Sudah Direview",
}

# Urutan transisi status yang valid dari tiap status
STATUS_TRANSITIONS = {
    "approached": ["replied", "ditolak"],
    "replied": ["scheduled", "ditolak"],
    "scheduled": ["visited", "batal", "scheduled"],  # scheduled->scheduled = reschedule
    "visited": ["content_uploaded"],
    "content_uploaded": ["performance_reviewed"],
    "performance_reviewed": [],
    "ditolak": [],
    "batal": [],
}
