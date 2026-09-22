"""
Alur setelah KOL "Sudah Berkunjung" dan kontennya naik, dipicu dari tombol
"🎬 Konten Sudah Naik" (lihat handlers/flow.py). Urutannya:

1. Link konten
2. Screenshot Google Review (opsional, /skip)
3. Screenshot halaman konten (wajib) -> bot baca angka-angka yang ada (Tesseract
   OCR, tanpa label pasti likes/komen/saves yang mana karena cuma ikon, jadi cuma
   ditampilkan sebagai bantuan) -> staff ketik manual views/likes/comments/shares/saves
4. Screenshot komentar di konten (opsional, /skip)

Setelah selesai, kolaborasi otomatis ditandai Content Uploaded lalu Performance Reviewed.
"""
import logging
from datetime import date

from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, CommandHandler,
    CallbackQueryHandler, filters,
)

import db
from utils.vision import extract_numbers_from_content_screenshot
from utils.sheets_sync import sync_if_configured

logger = logging.getLogger(__name__)

LINK, SS_REVIEW, SS_KONTEN, ANGKA, SS_KOMENTAR = range(5)


async def start_konten(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, kolaborasi_id_str, _ = query.data.split(":", 2)
    kolaborasi_id = int(kolaborasi_id_str)

    row = await db.get_kolaborasi(kolaborasi_id)
    if not row or row["status"] != "visited":
        await query.edit_message_text(
            "Kolaborasi ini belum di status Sudah Berkunjung, tidak bisa lanjut ke input konten."
        )
        return ConversationHandler.END

    context.user_data["konten_draft"] = {"kolaborasi_id": kolaborasi_id}
    await query.edit_message_text(f"Input konten untuk kolaborasi #{kolaborasi_id} ({row['nama']}).")
    await query.message.reply_text("Kirim link konten yang sudah upload.")
    return LINK


async def ask_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["konten_draft"]["link_konten"] = update.message.text.strip()
    await update.message.reply_text(
        "Kirim screenshot Google Review dari KOL ini (kalau ada), atau /skip."
    )
    return SS_REVIEW


async def ss_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    context.user_data["konten_draft"]["review_file_id"] = photo.file_id
    await update.message.reply_text("Sekarang kirim screenshot halaman konten (video/post) yang sudah upload.")
    return SS_KONTEN


async def skip_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Oke, dilewati. Kirim screenshot halaman konten (video/post) yang sudah upload.")
    return SS_KONTEN


async def ss_konten(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    file_bytes = await file.download_as_bytearray()

    draft = await extract_numbers_from_content_screenshot(bytes(file_bytes))
    context.user_data["konten_draft"]["konten_file_id"] = photo.file_id
    context.user_data["konten_draft"]["konten_ocr"] = draft

    numbers = draft.get("numbers") if draft else None
    if numbers:
        await update.message.reply_text(
            "Angka yang kebaca dari screenshot (cek ulang, urutan belum tentu sesuai likes/komen/saves): "
            + ", ".join(str(n) for n in numbers)
        )
    else:
        await update.message.reply_text("Tidak ada angka yang kebaca otomatis dari screenshot ini, isi manual ya.")

    await update.message.reply_text(
        "Ketik jumlah views, likes, comments, shares, saves dipisah spasi, urut seperti itu.\n"
        "Contoh: 15000 1200 85 30 40\n"
        "shares & saves boleh diisi '-' kalau tidak ada datanya, tapi tetap isi semua posisi, "
        "misal: 15000 1200 85 - -"
    )
    return ANGKA


async def skip_konten_impossible(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Screenshot halaman konten wajib dikirim (sumber utama data performa), tidak bisa di-skip.")
    return SS_KONTEN


async def input_angka(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = update.message.text.strip().split()
    if len(parts) < 3:
        await update.message.reply_text("Minimal isi views, likes, comments. Contoh: 15000 1200 85")
        return ANGKA
    try:
        def parse(x):
            return None if x == "-" else int(x.replace(".", "").replace(",", ""))
        views = parse(parts[0])
        likes = parse(parts[1])
        comments = parse(parts[2])
        shares = parse(parts[3]) if len(parts) > 3 else None
        saves = parse(parts[4]) if len(parts) > 4 else None
    except ValueError:
        await update.message.reply_text("Semua harus angka (atau '-'), coba lagi.")
        return ANGKA

    context.user_data["konten_draft"].update(
        views=views, likes=likes, comments=comments, shares=shares, saves=saves
    )
    await update.message.reply_text("Terakhir, kirim screenshot komentar di konten ini (opsional), atau /skip.")
    return SS_KOMENTAR


async def ss_komentar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    context.user_data["konten_draft"]["komentar_file_id"] = photo.file_id
    return await _finish(update, context)


async def skip_komentar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _finish(update, context)


async def _finish(update, context):
    draft = context.user_data["konten_draft"]
    kolaborasi_id = draft["kolaborasi_id"]
    user_id = update.effective_user.id

    row = await db.get_kolaborasi(kolaborasi_id)

    await db.update_status(
        kolaborasi_id, "content_uploaded", user_id,
        link_konten=draft.get("link_konten"), tanggal_upload=date.today(),
    )

    if draft.get("review_file_id"):
        await db.save_screenshot(
            kol_id=row["kol_id"], kolaborasi_id=kolaborasi_id, jenis="google_review",
            telegram_file_id=draft["review_file_id"], ocr_raw_text=None, uploaded_by=user_id,
        )
    if draft.get("konten_file_id"):
        ocr = draft.get("konten_ocr") or {}
        await db.save_screenshot(
            kol_id=row["kol_id"], kolaborasi_id=kolaborasi_id, jenis="konten_page",
            telegram_file_id=draft["konten_file_id"], ocr_raw_text=ocr.get("raw_text"), uploaded_by=user_id,
        )
    if draft.get("komentar_file_id"):
        await db.save_screenshot(
            kol_id=row["kol_id"], kolaborasi_id=kolaborasi_id, jenis="komentar",
            telegram_file_id=draft["komentar_file_id"], ocr_raw_text=None, uploaded_by=user_id,
        )

    await db.save_performa(
        kolaborasi_id, draft.get("views"), draft.get("likes"), draft.get("comments"),
        draft.get("shares"), draft.get("saves"), None, user_id,
    )
    await db.update_status(kolaborasi_id, "performance_reviewed", user_id)
    await sync_if_configured()

    await update.message.reply_text(
        f"Selesai. Kolaborasi #{kolaborasi_id} ({row['nama']}) ditandai Performa Sudah Direview.\n"
        f"views={draft.get('views')}, likes={draft.get('likes')}, comments={draft.get('comments')}, "
        f"shares={draft.get('shares') or '-'}, saves={draft.get('saves') or '-'}"
    )
    context.user_data.pop("konten_draft", None)
    return ConversationHandler.END


async def batal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("konten_draft", None)
    await update.message.reply_text("Input konten dibatalkan.")
    return ConversationHandler.END


def build_conversation_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_konten, pattern=r"^act:\d+:konten$")],
        states={
            LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_link)],
            SS_REVIEW: [
                MessageHandler(filters.PHOTO, ss_review),
                CommandHandler("skip", skip_review),
            ],
            SS_KONTEN: [
                MessageHandler(filters.PHOTO, ss_konten),
                CommandHandler("skip", skip_konten_impossible),
            ],
            ANGKA: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_angka)],
            SS_KOMENTAR: [
                MessageHandler(filters.PHOTO, ss_komentar),
                CommandHandler("skip", skip_komentar),
            ],
        },
        fallbacks=[CommandHandler("batal", batal)],
        name="konten_conversation",
    )
