"""
Ekstraksi data dari screenshot profil TikTok/Instagram pakai AI vision.
Hasilnya cuma DRAFT — staff tetap wajib konfirmasi/koreksi sebelum disimpan.
"""
import base64
import json
import logging

from config import OPENAI_API_KEY, VISION_MODEL

logger = logging.getLogger(__name__)

PROMPT = """Kamu membaca screenshot halaman profil TikTok atau Instagram.
Ambil informasi berikut kalau kelihatan di gambar, dan balas HANYA dalam JSON:
{
  "username": "...",
  "followers": <angka, tanpa titik/koma. konversi 12.3K -> 12300, 1.2M -> 1200000>,
  "bio": "...",
  "niche_tebakan": "tebakan kategori konten dari bio/isi profil, contoh: food, lifestyle, travel"
}
Kalau salah satu field tidak kelihatan, isi null. Jangan tambahkan teks lain di luar JSON."""


async def extract_profile_from_screenshot(image_bytes: bytes) -> dict:
    """Return dict dari hasil OCR, atau dict kosong kalau OCR gagal/tidak aktif."""
    if not OPENAI_API_KEY:
        return {}

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        b64 = base64.b64encode(image_bytes).decode("utf-8")

        response = await client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        },
                    ],
                }
            ],
            max_tokens=300,
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(raw)
    except Exception:
        logger.exception("Gagal ekstraksi screenshot dengan vision model")
        return {}
