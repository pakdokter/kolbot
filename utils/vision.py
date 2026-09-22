"""
Ekstraksi data dari screenshot pakai Tesseract OCR (lokal, gratis).
Hasilnya selalu DRAFT KASAR — staff tetap wajib konfirmasi/koreksi.
Niche/kategori TIDAK pernah ditebak otomatis, staff isi manual sepenuhnya.
"""
import io
import logging
import re

logger = logging.getLogger(__name__)

USERNAME_PATTERN = re.compile(r"@([A-Za-z0-9._]{2,30})")

STAT_KEYWORDS = {
    "followers": r"(?:followers|pengikut)",
    "following": r"(?:following|mengikuti)",
    "likes": r"(?:likes|suka)",
}

_SHORTHAND = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000, "rb": 1_000, "jt": 1_000_000}
_NUMBER_TOKEN = r"[\d][\d.,]*\s*[kKmMbB]?"


def _to_number(raw: str):
    """
    "2,047" atau "12.345" (tanpa huruf K/M/B di belakang) itu angka utuh dengan
    titik/koma sebagai pemisah ribuan -> dibuang semua, bukan dianggap desimal.
    "12.3K" / "1,2rb" (ada huruf shorthand) -> titik/koma di situ baru dianggap desimal.
    """
    raw = raw.strip()
    match = re.match(r"^([\d.,]+)\s*([a-zA-Z]{0,2})$", raw)
    if not match:
        digits = re.sub(r"[^\d]", "", raw)
        return int(digits) if digits else None

    number_part, suffix = match.groups()
    suffix = suffix.lower()

    if suffix in _SHORTHAND:
        normalized = number_part.replace(",", ".")
        head, _, tail = normalized.rpartition(".")
        if head:
            normalized = head.replace(".", "") + "." + tail
        try:
            value = float(normalized)
        except ValueError:
            return None
        return int(value * _SHORTHAND[suffix])

    digits = re.sub(r"[^\d]", "", number_part)
    return int(digits) if digits else None


def _guess_stat(text: str, keyword_pattern: str):
    """
    Cari angka yang berkaitan dengan sebuah label (followers/following/likes) di hasil OCR.
    Dua pola yang ditangani:
    1. Angka & label nempel satu baris, misal "12.3K Followers".
    2. Angka & label di baris terpisah tapi sejajar posisinya, misal baris
       "2 12 2,047" lalu baris "Following Followers Likes" -> ambil angka pada
       posisi index yang sama dengan posisi kata label itu.
    """
    lines = [l for l in text.splitlines() if l.strip()]

    for i, line in enumerate(lines):
        if not re.search(keyword_pattern, line, re.IGNORECASE):
            continue

        same_line_numbers = [
            c for c in re.findall(_NUMBER_TOKEN, line)
            if not re.search(keyword_pattern, c, re.IGNORECASE)
        ]
        if same_line_numbers:
            value = _to_number(same_line_numbers[0])
            if value is not None:
                return value

        if i > 0:
            label_tokens = line.split()
            label_idx = next(
                (j for j, t in enumerate(label_tokens) if re.fullmatch(keyword_pattern, t, re.IGNORECASE)),
                None,
            )
            number_tokens = re.findall(_NUMBER_TOKEN, lines[i - 1])
            if label_idx is not None and label_idx < len(number_tokens):
                value = _to_number(number_tokens[label_idx])
                if value is not None:
                    return value
            if number_tokens:
                value = _to_number(number_tokens[-1])
                if value is not None:
                    return value
    return None


def _guess_username(text: str):
    match = USERNAME_PATTERN.search(text)
    return match.group(1) if match else None


async def extract_profile_from_screenshot(image_bytes: bytes) -> dict:
    """
    Return dict draft: {"username", "followers", "following", "likes", "raw_text"}
    atau dict kosong kalau OCR gagal / tidak terbaca sama sekali.
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
            "followers": _guess_stat(raw_text, STAT_KEYWORDS["followers"]),
            "following": _guess_stat(raw_text, STAT_KEYWORDS["following"]),
            "likes": _guess_stat(raw_text, STAT_KEYWORDS["likes"]),
            "raw_text": raw_text.strip(),
        }
    except Exception:
        logger.exception("Gagal ekstraksi screenshot profil dengan Tesseract")
        return {}


async def extract_numbers_from_content_screenshot(image_bytes: bytes) -> dict:
    """
    Untuk screenshot halaman konten (video/postingan). Berbeda dari screenshot profil,
    angka likes/komen/saves di halaman konten biasanya cuma nempel ikon tanpa teks label,
    jadi tidak bisa ditandai otomatis per-field. Fungsi ini cuma mengembalikan semua angka
    yang kebaca (urut dari atas ke bawah) sebagai bahan bantu buat staff isi manual.
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

        numbers = []
        for tok in re.findall(_NUMBER_TOKEN, raw_text):
            value = _to_number(tok)
            if value is not None and value not in numbers:
                numbers.append(value)

        return {"numbers": numbers, "raw_text": raw_text.strip()}
    except Exception:
        logger.exception("Gagal ekstraksi screenshot konten dengan Tesseract")
        return {}
