import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]

# Dipakai untuk ekstraksi data dari screenshot profil TikTok/Instagram.
# Kosongkan OPENAI_API_KEY kalau mau matikan fitur OCR (bot tetap jalan, staff isi manual semua).
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
VISION_MODEL = os.environ.get("VISION_MODEL", "gpt-4o-mini")

# Google Sheets sync (opsional). Kosongkan kalau belum mau dipakai.
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
