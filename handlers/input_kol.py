"""
Alur /input_kol: staff upload screenshot TikTok & Instagram (opsional, bisa /skip),
bot coba baca datanya sebagai draft, lalu staff mengisi/mengoreksi tiap field secara
berurutan. Field OCR ditampilkan sebagai hint, staff tetap wajib mengetik nilainya sendiri.
"""
import logging

from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, CommandHandler, filters,
)

import db
from utils.vision import extract_profile_from_screenshot
from utils.sheets_sync import sync_if_configured

logger = logging.getLogger(__name__)

(
    SS_TIKTOK, SS_IG,
    F_NAMA, F_TIKTOK_USER, F_IG_USER, F_FOLLOWERS_TIKTOK, F_FOLLOWERS_IG,
    F_NICHE, F_DOMISILI, F_DEMOGRAFI, F_KONTAK,
    F_TIPE_KOLAB, F_PREFERENSI, F_PIC, F_CATATAN,
    CONFIRM,
) = range(16)

FIELD_ORDER = [
    (F_NAMA, "nama", "Nama KOL?"),
    (F_TIKTOK_USER, "tiktok_username", "Username TikTok? (kosongkan dengan '-' kalau tidak ada)"),
    (F_IG_USER, "ig_username", "Username Instagram? ('-' kalau tidak ada)"),
    (F_FOLLOWERS_TIKTOK, "followers_tiktok", "Jumlah followers TikTok? (angka saja, '-' kalau tidak tahu)"),
    (F_FOLLOWERS_IG, "followers_ig", "Jumlah followers Instagram? (angka saja, '-' kalau tidak tahu)"),
    (F_NICHE, "niche", "Niche/kategori konten KOL? (misal: food, lifestyle, travel)"),
    (F_DOMISILI, "domisili", "Domisili KOL? (misal: Lombok Timur, luar NTB, dll)"),
    (F_DEMOGRAFI, "demografi_audiens", "Perkiraan demografi audiens? ('-' kalau tidak ada info)"),
    (F_KONTAK, "kontak", "Kontak KOL (WA/email)? ('-' kalau belum ada)"),
    (F_TIPE_KOLAB, "tipe_kolaborasi", "Tipe kolaborasi? (barter/paid/lainnya)"),
    (F_PREFERENSI, "preferensi_konten", "Preferensi konten? (reel, video review, story, dll)"),
    (F_PIC, "pic", "PIC internal yang approach KOL ini?"),
    (F_CATATAN, "catatan", "Catatan tambahan? ('-' kalau tidak ada)"),
]
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
        await update.message.reply_text(f"Terbaca (cek ulang ya): {preview or 'username/followers tidak terbaca, teks lain ada di raw text'}")
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
        "followers_ig": ig_hint.get("followers"),
        # niche sengaja tidak ditebak otomatis, selalu diisi manual oleh staff
    }
    key, field, prompt = FIELD_ORDER[0]
    await _ask(update, context, key)
    return key


async def _ask(update, context, state):
    field_map = {k: (name, prompt) for k, name, prompt in FIELD_ORDER}
    name, prompt = field_map[state]
    hint = context.user_data.get("_field_hints", {}).get(name)
    if hint:
        prompt = f"{prompt}\n(hasil baca screenshot: {hint} — ketik ulang untuk konfirmasi/koreksi)"
    await update.message.reply_text(prompt)


def make_field_handler(state):
    name = {k: n for k, n, _ in FIELD_ORDER}[state]

    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        value = None if text == "-" else text
        if name in ("followers_tiktok", "followers_ig") and value is not None:
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
    lines = [f"- {name}: {draft.get(name) or '-'}" for _, name, _ in FIELD_ORDER]
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

    await update.message.reply_text(
        f"Tersimpan. KOL #{kol_id}, kolaborasi #{kolaborasi_id} dengan status 'Sudah Diapproach'."
    )
    await sync_if_configured()
    context.user_data.clear()
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
    for key, name, _ in FIELD_ORDER:
        states[key] = [MessageHandler(filters.TEXT & ~filters.COMMAND, make_field_handler(key))]
    states[CONFIRM] = [CommandHandler("simpan", simpan), CommandHandler("batal", batal)]

    return ConversationHandler(
        entry_points=[CommandHandler("input_kol", start)],
        states=states,
        fallbacks=[CommandHandler("batal", batal)],
        name="input_kol_conversation",
    )
