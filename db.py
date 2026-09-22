import asyncpg
from config import DATABASE_URL

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return _pool


async def init_db():
    pool = await get_pool()
    with open("schema.sql", "r") as f:
        schema = f.read()
    async with pool.acquire() as conn:
        await conn.execute(schema)


# ---------- KOL ----------

async def create_kol(nama, tiktok_username, ig_username, followers_tiktok,
                      followers_ig, following_tiktok, following_ig,
                      likes_tiktok, likes_ig, niche, engagement_rate, domisili,
                      demografi_audiens, kontak, catatan, created_by):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO kol (nama, tiktok_username, ig_username, followers_tiktok,
                              followers_ig, following_tiktok, following_ig,
                              likes_tiktok, likes_ig, niche, engagement_rate, domisili,
                              demografi_audiens, kontak, catatan, created_by)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
            RETURNING id
            """,
            nama, tiktok_username, ig_username, followers_tiktok, followers_ig,
            following_tiktok, following_ig, likes_tiktok, likes_ig,
            niche, engagement_rate, domisili, demografi_audiens, kontak, catatan,
            created_by,
        )
        return row["id"]


async def find_kol_by_username(username: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT * FROM kol
            WHERE lower(tiktok_username) = lower($1)
               OR lower(ig_username) = lower($1)
               OR lower(nama) = lower($1)
            ORDER BY id DESC LIMIT 1
            """,
            username.lstrip("@"),
        )


async def get_kol(kol_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM kol WHERE id = $1", kol_id)


# ---------- Kolaborasi ----------

async def create_kolaborasi(kol_id, tipe_kolaborasi, preferensi_konten, pic, created_by):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO kolaborasi (kol_id, tipe_kolaborasi, preferensi_konten, pic, status, created_by)
            VALUES ($1,$2,$3,$4,'approached',$5)
            RETURNING id
            """,
            kol_id, tipe_kolaborasi, preferensi_konten, pic, created_by,
        )
        kolaborasi_id = row["id"]
        await conn.execute(
            """
            INSERT INTO status_history (kolaborasi_id, status_lama, status_baru, changed_by)
            VALUES ($1, NULL, 'approached', $2)
            """,
            kolaborasi_id, created_by,
        )
        return kolaborasi_id


async def update_status(kolaborasi_id, status_baru, changed_by, catatan=None,
                         tanggal_kunjungan=None, link_konten=None, tanggal_upload=None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT status FROM kolaborasi WHERE id = $1", kolaborasi_id)
        status_lama = row["status"] if row else None
        fields = ["status = $2", "updated_at = now()"]
        values = [kolaborasi_id, status_baru]
        idx = 3
        if tanggal_kunjungan is not None:
            fields.append(f"tanggal_kunjungan = ${idx}")
            values.append(tanggal_kunjungan)
            idx += 1
        if link_konten is not None:
            fields.append(f"link_konten = ${idx}")
            values.append(link_konten)
            idx += 1
        if tanggal_upload is not None:
            fields.append(f"tanggal_upload = ${idx}")
            values.append(tanggal_upload)
            idx += 1
        await conn.execute(
            f"UPDATE kolaborasi SET {', '.join(fields)} WHERE id = $1", *values
        )
        await conn.execute(
            """
            INSERT INTO status_history (kolaborasi_id, status_lama, status_baru, catatan, changed_by)
            VALUES ($1,$2,$3,$4,$5)
            """,
            kolaborasi_id, status_lama, status_baru, catatan, changed_by,
        )


async def get_kolaborasi(kolaborasi_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT kl.*, k.nama, k.tiktok_username, k.ig_username
            FROM kolaborasi kl JOIN kol k ON k.id = kl.kol_id
            WHERE kl.id = $1
            """,
            kolaborasi_id,
        )


async def list_by_status(status: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT kl.*, k.nama, k.tiktok_username, k.ig_username
            FROM kolaborasi kl JOIN kol k ON k.id = kl.kol_id
            WHERE kl.status = $1
            ORDER BY kl.updated_at DESC
            """,
            status,
        )


async def list_all_kolaborasi():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT kl.*, k.nama, k.tiktok_username, k.ig_username,
                   k.niche, k.domisili, k.kontak
            FROM kolaborasi kl JOIN kol k ON k.id = kl.kol_id
            ORDER BY kl.created_at DESC
            """
        )


async def list_kolaborasi_by_kol(kol_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM kolaborasi WHERE kol_id = $1 ORDER BY created_at DESC", kol_id
        )


# ---------- Screenshot ----------

async def save_screenshot(kol_id, kolaborasi_id, jenis, telegram_file_id, ocr_raw_text, uploaded_by):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO screenshot (kol_id, kolaborasi_id, jenis, telegram_file_id, ocr_raw_text, uploaded_by)
            VALUES ($1,$2,$3,$4,$5,$6)
            """,
            kol_id, kolaborasi_id, jenis, telegram_file_id, ocr_raw_text, uploaded_by,
        )


# ---------- Performa & Feedback ----------

async def save_performa(kolaborasi_id, views, likes, comments, shares, saves, catatan, input_by):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO performa (kolaborasi_id, views, likes, comments, shares, saves, catatan, input_by)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            """,
            kolaborasi_id, views, likes, comments, shares, saves, catatan, input_by,
        )


async def get_performa(kolaborasi_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM performa WHERE kolaborasi_id = $1 ORDER BY input_at DESC", kolaborasi_id
        )


async def save_feedback(kolaborasi_id, feedback_text, input_by):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO feedback (kolaborasi_id, feedback_text, input_by)
            VALUES ($1,$2,$3)
            """,
            kolaborasi_id, feedback_text, input_by,
        )


async def get_feedback(kolaborasi_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM feedback WHERE kolaborasi_id = $1 ORDER BY input_at DESC", kolaborasi_id
        )
