"""
Alur /input_kol: staff upload screenshot TikTok & Instagram (opsional, bisa /skip),
bot coba baca followers/following/likes + username sebagai draft (Tesseract OCR),
staff mengisi/koreksi tiap field secara berurutan, dikelompokkan per bagian biar
tidak jadi daftar panjang yang melelahkan dibaca satu per satu.

Setelah disimpan, bot langsung lanjut ke panel status berbasis tombol (lihat
handlers/flow.py) — bukan cuma "tersimpan, selesai".
"""
import logging

from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, CommandHandler, filters,
)

import db
from utils.vision import extract_profile_from_screenshot
from utils.sheets_sync import sync_if_configured
from handlers import flow

logger = logging.getLogger(__name__)

SS_TIKTOK, SS_IG = range(2)

# (state_offset, field_name, prompt, judul_section_atau_None)
# judul_section diisi hanya di field PERTAMA tiap section -> jadi header sebelum prompt-nya
_FIELD_DEFS = [
    ("nama", "Nama KOL?", "📋 Identitas & Platform"),
    ("tiktok_username", "Username TikTok? ('-' kalau tidak ada)", None),
    ("ig_username", "Username Instagram? ('-' kalau tidak ada)", None),
    ("followers_tiktok", "Followers TikTok? (angka saja, '-' kalau tidak tahu)", "📊 Statistik Akun"),
    ("following_tiktok", "Following TikTok? (angka saja, '-' kalau tidak tahu)", None),
    ("likes_tiktok", "Total Likes TikTok? (angka saja, '-' kalau tidak tahu)", None),
    ("followers_ig", "Followers Instagram? (angka saja, '-' kalau tidak tahu)", None),
    ("following_ig", "Following Instagram? (angka saja, '-' kalau tidak tahu)", None),
    ("niche", "Niche/kategori konten KOL? (misal: food, lifestyle, travel)", "🎯 Profil Audiens"),
    ("domisili", "Domisili KOL? (misal: Lombok Timur, luar NTB, dll)", None),
    ("demografi_audiens", "Perkiraan demografi audiens? ('-' kalau tidak ada info)", None),
    ("kontak", "Kontak KOL (WA/email)? ('-' kalau belum ada)", None),
    ("tipe_kolaborasi", "Tipe kolaborasi? (barter/paid/lainnya)", "🤝 Kerja Sama"),
    ("preferensi_konten", "Preferensi konten? (reel, video review, story, dll)", None),
    ("pic", "PIC internal yang approach KOL ini?", None),
    ("catatan", "Catatan tambahan? ('-' kalau tidak ada)", None),
]
_NUMERIC_FIELDS = {"followers_tiktok", "following_tiktok", "likes_tiktok", "followers_ig", "following_ig"}

# state key tiap field = index + offset setelah SS_IG
FIELD_ORDER = [(i + 2, name, prompt, section) for i, (name, prompt, section) in enumerate(_FIELD_DEFS)]
CONFIRM = len(FIELD_ORDER) + 2
NEXT_STATE = {FIELD_ORDER[i][0]: FIELD_ORDER[i + 1][0] for i in range(len(FIELD_ORDER) - 1)}
NEXT_STATE[FIELD_ORDER[-1][0]] = CONFIRM


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["kol_draft"] = {}
    context.user_data["ocr_hints"] = {}
    await update.message.reply_text(
        "Input KOL baru.\n\n"
        "Kirim screenshot profil TikTok KOL ini (atau ketik /skip kalau tidak ada)."
    )
    return SS_TIKTOK


async def _handle_screenshot(update, context, jenis: str):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    file_bytes = await file.download_as_bytearray()

    draft = await extract_profile_from_screenshot(bytes(file_bytes))
    context.user_data["ocr_hints"][jenis] = draft
    context.user_data.setdefault("screenshots", []).append(
        {"jenis": jenis, "file_id": photo.file_id, "ocr_raw": draft}
    )
    if draft:
        preview = ", ".join(
            f"{k}={v}" for k, v in draft.items() if v and k != "raw_text"
        )
        await update.message.reply_text(
            f"Terbaca (cek ulang ya): {preview or 'username/angka tidak terbaca jelas'}"
        )
    else:
        await update.message.reply_text("Tidak berhasil membaca data dari screenshot, lanjut isi manual ya.")


async def ss_tiktok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_screenshot(update, context, "tiktok_profile")
    await update.message.reply_text("Sekarang kirim screenshot profil Instagram-nya (atau /skip).")
    return SS_IG


async def skip_ss_tiktok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Oke, dilewati. Sekarang kirim screenshot profil Instagram (atau /skip).")
    return SS_IG


async def ss_ig(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_screenshot(update, context, "ig_profile")
    return await _start_fields(update, context)


async def skip_ss_ig(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _start_fields(update, context)


async def _start_fields(update, context):
    hints = context.user_data.get("ocr_hints", {})
    tiktok_hint = hints.get("tiktok_profile", {}) or {}
    ig_hint = hints.get("ig_profile", {}) or {}
    context.user_data["_field_hints"] = {
        "tiktok_username": tiktok_hint.get("username"),
        "ig_username": ig_hint.get("username"),
        "followers_tiktok": tiktok_hint.get("followers"),
        "following_tiktok": tiktok_hint.get("following"),
        "likes_tiktok": tiktok_hint.get("likes"),
        "followers_ig": ig_hint.get("followers"),
        "following_ig": ig_hint.get("following"),
        # niche sengaja tidak ditebak otomatis, selalu diisi manual oleh staff
    }
    first_state, _, _, _ = FIELD_ORDER[0]
    await _ask(update, context, first_state)
    return first_state


async def _ask(update, context, state):
    field_map = {k: (name, prompt, section) for k, name, prompt, section in FIELD_ORDER}
    name, prompt, section = field_map[state]
    if section:
        await update.message.reply_text(f"— {section} —")
    hint = context.user_data.get("_field_hints", {}).get(name)
    if hint:
        prompt = f"{prompt}\n(hasil baca screenshot: {hint} — ketik ulang untuk konfirmasi/koreksi)"
    await update.message.reply_text(prompt)


def make_field_handler(state):
    name = {k: n for k, n, _, _ in FIELD_ORDER}[state]

    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        value = None if text == "-" else text
        if name in _NUMERIC_FIELDS and value is not None:
            try:
                value = int(value.replace(".", "").replace(",", ""))
            except ValueError:
                await update.message.reply_text("Angka tidak valid, coba lagi (angka saja, atau '-').")
                return state
        context.user_data["kol_draft"][name] = value

        next_state = NEXT_STATE[state]
        if next_state == CONFIRM:
            return await _show_confirmation(update, context)
        await _ask(update, context, next_state)
        return next_state

    return handler


async def _show_confirmation(update, context):
    draft = context.user_data["kol_draft"]
    lines = [f"- {name}: {draft.get(name) or '-'}" for _, name, _, _ in FIELD_ORDER]
    await update.message.reply_text(
        "Cek data sebelum disimpan:\n" + "\n".join(lines) +
        "\n\nKetik /simpan untuk simpan, atau /batal untuk membatalkan."
    )
    return CONFIRM


async def simpan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data["kol_draft"]
    user_id = update.effective_user.id

    existing = await db.find_kol_by_username(draft.get("tiktok_username") or draft.get("ig_username") or draft["nama"])
    if existing:
        kol_id = existing["id"]
    else:
        kol_id = await db.create_kol(
            nama=draft["nama"],
            tiktok_username=draft.get("tiktok_username"),
            ig_username=draft.get("ig_username"),
            followers_tiktok=draft.get("followers_tiktok"),
            followers_ig=draft.get("followers_ig"),
            following_tiktok=draft.get("following_tiktok"),
            following_ig=draft.get("following_ig"),
            likes_tiktok=draft.get("likes_tiktok"),
            likes_ig=None,
            niche=draft.get("niche"),
            engagement_rate=None,
            domisili=draft.get("domisili"),
            demografi_audiens=draft.get("demografi_audiens"),
            kontak=draft.get("kontak"),
            catatan=draft.get("catatan"),
            created_by=user_id,
        )

    kolaborasi_id = await db.create_kolaborasi(
        kol_id=kol_id,
        tipe_kolaborasi=draft.get("tipe_kolaborasi"),
        preferensi_konten=draft.get("preferensi_konten"),
        pic=draft.get("pic"),
        created_by=user_id,
    )

    for ss in context.user_data.get("screenshots", []):
        await db.save_screenshot(
            kol_id=kol_id,
            kolaborasi_id=kolaborasi_id,
            jenis=ss["jenis"],
            telegram_file_id=ss["file_id"],
            ocr_raw_text=str(ss["ocr_raw"]) if ss["ocr_raw"] else None,
            uploaded_by=user_id,
        )

    await sync_if_configured()
    await update.message.reply_text(
        f"Tersimpan. KOL #{kol_id}, kolaborasi #{kolaborasi_id} dengan status 'Sudah Diapproach'."
    )
    context.user_data.clear()

    # Lanjut langsung ke panel status berbasis tombol untuk kolaborasi yang baru dibuat
    await flow.show_panel(update.message.reply_text, kolaborasi_id)
    return ConversationHandler.END


async def batal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Input dibatalkan.")
    return ConversationHandler.END


def build_conversation_handler():
    states = {
        SS_TIKTOK: [
            MessageHandler(filters.PHOTO, ss_tiktok),
            CommandHandler("skip", skip_ss_tiktok),
        ],
        SS_IG: [
            MessageHandler(filters.PHOTO, ss_ig),
            CommandHandler("skip", skip_ss_ig),
        ],
    }
    for key, name, _, _ in FIELD_ORDER:
        states[key] = [MessageHandler(filters.TEXT & ~filters.COMMAND, make_field_handler(key))]
    states[CONFIRM] = [CommandHandler("simpan", simpan), CommandHandler("batal", batal)]

    return ConversationHandler(
        entry_points=[CommandHandler("input_kol", start)],
        states=states,
        fallbacks=[CommandHandler("batal", batal)],
        name="input_kol_conversation",
    )
