"""
Panel status berbasis tombol (inline keyboard) — pengganti command manual
/reply /tolak /jadwal dst. Bot cuma nampilin tombol yang valid buat status
saat ini (kayak flowchart), staff tinggal tap, asumsi diisi berurutan.

Alur:
  approached -> [Sudah Membalas]/[Ditolak]/[Belum Dibaca]
  replied    -> (isi tanggal via teks) -> scheduled
  scheduled  -> [Sudah Berkunjung]/[Reschedule]/[Batalkan]
  visited    -> [Konten Sudah Naik] (lanjut ke handlers/konten.py)

Command /reply /tolak /jadwal dst di handlers/status.py tetap ada sebagai
jalur manual/cadangan buat yang lebih suka ketik command langsung.
"""
import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

import db
from config import STATUS_LABELS
from utils.sheets_sync import sync_if_configured

logger = logging.getLogger(__name__)


def _kb(kolaborasi_id, buttons):
    rows = [[InlineKeyboardButton(label, callback_data=f"act:{kolaborasi_id}:{action}")] for label, action in buttons]
    return InlineKeyboardMarkup(rows)


def panel_for_status(kolaborasi_id, status):
    """Return (text, keyboard_atau_None) sesuai status kolaborasi saat ini."""
    label = STATUS_LABELS.get(status, status)

    if status == "approached":
        return (
            f"Kolaborasi #{kolaborasi_id} — status: {label}\nApakah KOL ini sudah membalas?",
            _kb(kolaborasi_id, [
                ("✅ Sudah Membalas", "reply"),
                ("❌ Ditolak", "tolak"),
                ("⏳ Belum Dibaca", "belum"),
            ]),
        )
    if status == "replied":
        return (
            f"Kolaborasi #{kolaborasi_id} — status: {label}\n"
            f"Kirim tanggal jadwal kunjungan (format YYYY-MM-DD).",
            None,
        )
    if status == "scheduled":
        return (
            f"Kolaborasi #{kolaborasi_id} — status: {label}\nUpdate kunjungan:",
            _kb(kolaborasi_id, [
                ("🏠 Sudah Berkunjung", "visited"),
                ("🔁 Reschedule", "reschedule"),
                ("🚫 Batalkan", "batal"),
            ]),
        )
    if status == "visited":
        return (
            f"Kolaborasi #{kolaborasi_id} — status: {label}\nKalau kontennya sudah naik, lanjut isi datanya:",
            _kb(kolaborasi_id, [("🎬 Konten Sudah Naik", "konten")]),
        )
    return (f"Kolaborasi #{kolaborasi_id} — status: {label}. Tidak ada aksi lanjutan lewat menu ini.", None)


async def show_panel(message_sender, kolaborasi_id):
    """message_sender: callable async (text, reply_markup=None), biasanya
    update.message.reply_text atau query.message.reply_text."""
    row = await db.get_kolaborasi(kolaborasi_id)
    if not row:
        await message_sender(f"Kolaborasi #{kolaborasi_id} tidak ditemukan.")
        return
    text, kb = panel_for_status(kolaborasi_id, row["status"])
    if kb:
        await message_sender(text, reply_markup=kb)
    else:
        await message_sender(text)


async def panel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Pakai: /panel <kolaborasi_id>")
        return
    try:
        kolaborasi_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("kolaborasi_id harus angka.")
        return
    await show_panel(update.message.reply_text, kolaborasi_id)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        _, kolaborasi_id_str, action = query.data.split(":", 2)
        kolaborasi_id = int(kolaborasi_id_str)
    except ValueError:
        return

    row = await db.get_kolaborasi(kolaborasi_id)
    if not row:
        await query.edit_message_text(f"Kolaborasi #{kolaborasi_id} tidak ditemukan.")
        return

    user_id = update.effective_user.id

    if action == "reply" and row["status"] == "approached":
        await db.update_status(kolaborasi_id, "replied", user_id)
        await sync_if_configured()
        await query.edit_message_text(f"Kolaborasi #{kolaborasi_id} ({row['nama']}) ditandai Sudah Membalas.")
        context.user_data["pending_action"] = {"kolaborasi_id": kolaborasi_id, "action": "jadwal"}
        await query.message.reply_text("Kapan jadwal kunjungannya? Kirim tanggal format YYYY-MM-DD.")
        return

    if action == "tolak" and row["status"] in ("approached", "replied"):
        context.user_data["pending_action"] = {"kolaborasi_id": kolaborasi_id, "action": "tolak_alasan"}
        await query.edit_message_text(f"Kolaborasi #{kolaborasi_id} ({row['nama']}) — Ditolak.")
        await query.message.reply_text("Alasan ditolak? (ketik alasannya, atau '-' kalau tanpa alasan)")
        return

    if action == "belum" and row["status"] == "approached":
        await query.edit_message_text(
            f"Oke, kolaborasi #{kolaborasi_id} ({row['nama']}) tetap di status Sudah Diapproach.\n"
            f"Buka lagi kapan saja dengan /panel {kolaborasi_id}."
        )
        return

    if action == "visited" and row["status"] == "scheduled":
        await db.update_status(kolaborasi_id, "visited", user_id)
        await sync_if_configured()
        await query.edit_message_text(f"Kolaborasi #{kolaborasi_id} ({row['nama']}) ditandai Sudah Berkunjung.")
        text, kb = panel_for_status(kolaborasi_id, "visited")
        await query.message.reply_text(text, reply_markup=kb)
        return

    if action == "reschedule" and row["status"] == "scheduled":
        context.user_data["pending_action"] = {"kolaborasi_id": kolaborasi_id, "action": "reschedule"}
        await query.edit_message_text(f"Kolaborasi #{kolaborasi_id} ({row['nama']}) — reschedule jadwal.")
        await query.message.reply_text("Tanggal jadwal baru? Format YYYY-MM-DD.")
        return

    if action == "batal" and row["status"] == "scheduled":
        context.user_data["pending_action"] = {"kolaborasi_id": kolaborasi_id, "action": "batal_alasan"}
        await query.edit_message_text(f"Kolaborasi #{kolaborasi_id} ({row['nama']}) — dibatalkan.")
        await query.message.reply_text("Alasan pembatalan? (ketik alasannya, atau '-' kalau tanpa alasan)")
        return

    # action == "konten" ditangani ConversationHandler terpisah di handlers/konten.py,
    # tidak sampai ke sini karena pattern CallbackQueryHandler di bawah mengecualikannya.


async def handle_pending_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menangani input teks lanjutan dari tombol (tanggal jadwal, alasan tolak/batal).
    No-op kalau tidak ada pending_action, supaya tidak mengganggu handler lain
    (misal ConversationHandler /input_kol yang juga menunggu teks)."""
    pending = context.user_data.get("pending_action")
    if not pending:
        return

    kolaborasi_id = pending["kolaborasi_id"]
    action = pending["action"]
    text = update.message.text.strip()
    user_id = update.effective_user.id

    if action in ("jadwal", "reschedule"):
        try:
            tanggal = datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            await update.message.reply_text("Format tanggal salah, coba lagi (YYYY-MM-DD).")
            return
        await db.update_status(kolaborasi_id, "scheduled", user_id, tanggal_kunjungan=tanggal)
        await sync_if_configured()
        context.user_data.pop("pending_action", None)
        row = await db.get_kolaborasi(kolaborasi_id)
        await update.message.reply_text(f"Kolaborasi #{kolaborasi_id} ({row['nama']}) terjadwal {tanggal}.")
        text_panel, kb = panel_for_status(kolaborasi_id, "scheduled")
        await update.message.reply_text(text_panel, reply_markup=kb)
        return

    if action in ("tolak_alasan", "batal_alasan"):
        alasan = None if text == "-" else text
        status_baru = "ditolak" if action == "tolak_alasan" else "batal"
        await db.update_status(kolaborasi_id, status_baru, user_id, catatan=alasan)
        await sync_if_configured()
        context.user_data.pop("pending_action", None)
        await update.message.reply_text("Tersimpan.")
        return


def build_handlers():
    return [
        CallbackQueryHandler(button_callback, pattern=r"^act:\d+:(?!konten$)\w+$"),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pending_text),
    ]
