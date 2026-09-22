"""
Ekstraksi data dari screenshot profil TikTok/Instagram pakai Tesseract OCR (lokal, gratis).
Hasilnya cuma DRAFT KASAR (username & followers) — staff tetap wajib konfirmasi/koreksi.
Niche/kategori TIDAK ditebak otomatis, staff isi manual sepenuhnya.
"""
import io
import logging
import re

logger = logging.getLogger(__name__)

FOLLOWERS_KEYWORDS = r"(?:followers|pengikut|pengikuts?)"
USERNAME_PATTERN = re.compile(r"@([A-Za-z0-9._]{2,30})")

_SHORTHAND = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000, "rb": 1_000, "jt": 1_000_000}


def _to_number(raw: str):
    raw = raw.strip().replace(",", ".")
    match = re.match(r"^(\d+(?:\.\d+)?)\s*([a-zA-Z]{0,2})$", raw)
    if not match:
        digits = re.sub(r"[^\d]", "", raw)
        return int(digits) if digits else None
    number, suffix = match.groups()
    suffix = suffix.lower()
    value = float(number)
    if suffix in _SHORTHAND:
        value *= _SHORTHAND[suffix]
    return int(value)


def _guess_followers(text: str):
    """
    Cari angka followers di hasil OCR. Dua pola yang ditangani:
    1. Angka & label nempel satu baris, misal "12.3K Followers".
    2. Profil TikTok/IG umumnya taruh angka & label di baris terpisah tapi urutan
       sejajar, misal baris "2 12 2,047" lalu baris "Following Followers Likes"
       -> ambil angka pada posisi index yang sama dengan kata "Followers".
    """
    lines = [l for l in text.splitlines() if l.strip()]
    number_token = r"[\d][\d.,]*\s*[kKmMbB]?"

    for i, line in enumerate(lines):
        if not re.search(FOLLOWERS_KEYWORDS, line, re.IGNORECASE):
            continue

        # Pola 1: angka & kata kunci di baris yang sama
        same_line_numbers = [
            c for c in re.findall(number_token, line)
            if not re.search(FOLLOWERS_KEYWORDS, c, re.IGNORECASE)
        ]
        if same_line_numbers:
            value = _to_number(same_line_numbers[0])
            if value:
                return value

        # Pola 2: cocokkan posisi kata "followers/pengikut" di baris label
        # dengan posisi angka yang sama di baris sebelumnya
        if i > 0:
            label_tokens = line.split()
            label_idx = next(
                (j for j, t in enumerate(label_tokens) if re.fullmatch(FOLLOWERS_KEYWORDS, t, re.IGNORECASE)),
                None,
            )
            number_tokens = re.findall(number_token, lines[i - 1])
            if label_idx is not None and label_idx < len(number_tokens):
                value = _to_number(number_tokens[label_idx])
                if value:
                    return value
            if number_tokens:
                value = _to_number(number_tokens[-1])
                if value:
                    return value
    return None


def _guess_username(text: str):
    match = USERNAME_PATTERN.search(text)
    return match.group(1) if match else None


async def extract_profile_from_screenshot(image_bytes: bytes) -> dict:
    """
    Return dict draft: {"username": ..., "followers": ..., "raw_text": ...}
    atau dict kosong kalau OCR gagal / tesseract tidak terpasang.
    Field "niche" sengaja tidak ada di sini — niche selalu diisi manual oleh staff.
    """
    try:
        import pytesseract
        from PIL import Image, ImageOps

        image = Image.open(io.BytesIO(image_bytes))
        image = ImageOps.grayscale(image)
        image = ImageOps.autocontrast(image)

        raw_text = pytesseract.image_to_string(image)
        if not raw_text.strip():
            return {}

        return {
            "username": _guess_username(raw_text),
            "followers": _guess_followers(raw_text),
            "raw_text": raw_text.strip(),
        }
    except Exception:
        logger.exception("Gagal ekstraksi screenshot dengan Tesseract")
        return {}
