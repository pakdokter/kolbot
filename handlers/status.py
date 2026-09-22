"""
Command untuk update status kolaborasi:
/reply <kolaborasi_id>
/jadwal <kolaborasi_id> <YYYY-MM-DD>
/reschedule <kolaborasi_id> <YYYY-MM-DD> [alasan]
/tolak <kolaborasi_id> [alasan]
/batalkan <kolaborasi_id> [alasan]
/berkunjung <kolaborasi_id>
/upload <kolaborasi_id> <link_konten>
"""
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

import db
from config import STATUS_LABELS
from utils.sheets_sync import sync_if_configured


def _parse_args(text: str):
    parts = text.split(maxsplit=2)
    return parts[1:] if len(parts) > 1 else []


async def _require_status(update, kolaborasi_id, expected: list[str]):
    row = await db.get_kolaborasi(kolaborasi_id)
    if not row:
        await update.message.reply_text(f"Kolaborasi #{kolaborasi_id} tidak ditemukan.")
        return None
    if row["status"] not in expected:
        await update.message.reply_text(
            f"Status kolaborasi #{kolaborasi_id} saat ini '{STATUS_LABELS.get(row['status'], row['status'])}', "
            f"tidak bisa langsung diubah ke langkah ini."
        )
        return None
    return row


async def reply_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Pakai: /reply <kolaborasi_id>")
        return
    kolaborasi_id = int(args[0])
    row = await _require_status(update, kolaborasi_id, ["approached"])
    if not row:
        return
    await db.update_status(kolaborasi_id, "replied", update.effective_user.id)
    await update.message.reply_text(f"Kolaborasi #{kolaborasi_id} ({row['nama']}) ditandai Sudah Membalas.")
    await sync_if_configured()


async def jadwal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Pakai: /jadwal <kolaborasi_id> <YYYY-MM-DD>")
        return
    kolaborasi_id = int(args[0])
    try:
        tanggal = datetime.strptime(args[1], "%Y-%m-%d").date()
    except ValueError:
        await update.message.reply_text("Format tanggal salah, pakai YYYY-MM-DD.")
        return
    row = await _require_status(update, kolaborasi_id, ["replied", "scheduled"])
    if not row:
        return
    await db.update_status(kolaborasi_id, "scheduled", update.effective_user.id, tanggal_kunjungan=tanggal)
    await update.message.reply_text(f"Kolaborasi #{kolaborasi_id} ({row['nama']}) dijadwalkan {tanggal}.")
    await sync_if_configured()


async def reschedule_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Pakai: /reschedule <kolaborasi_id> <YYYY-MM-DD> [alasan]")
        return
    kolaborasi_id = int(args[0])
    try:
        tanggal = datetime.strptime(args[1], "%Y-%m-%d").date()
    except ValueError:
        await update.message.reply_text("Format tanggal salah, pakai YYYY-MM-DD.")
        return
    alasan = " ".join(args[2:]) if len(args) > 2 else None
    row = await _require_status(update, kolaborasi_id, ["scheduled"])
    if not row:
        return
    await db.update_status(kolaborasi_id, "scheduled", update.effective_user.id, catatan=alasan, tanggal_kunjungan=tanggal)
    await update.message.reply_text(f"Jadwal kolaborasi #{kolaborasi_id} ({row['nama']}) diubah ke {tanggal}.")
    await sync_if_configured()


async def tolak_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Pakai: /tolak <kolaborasi_id> [alasan]")
        return
    kolaborasi_id = int(args[0])
    alasan = " ".join(args[1:]) if len(args) > 1 else None
    row = await _require_status(update, kolaborasi_id, ["approached", "replied"])
    if not row:
        return
    await db.update_status(kolaborasi_id, "ditolak", update.effective_user.id, catatan=alasan)
    await update.message.reply_text(f"Kolaborasi #{kolaborasi_id} ({row['nama']}) ditandai Ditolak.")
    await sync_if_configured()


async def batalkan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Pakai: /batalkan <kolaborasi_id> [alasan]")
        return
    kolaborasi_id = int(args[0])
    alasan = " ".join(args[1:]) if len(args) > 1 else None
    row = await _require_status(update, kolaborasi_id, ["scheduled"])
    if not row:
        return
    await db.update_status(kolaborasi_id, "batal", update.effective_user.id, catatan=alasan)
    await update.message.reply_text(f"Kolaborasi #{kolaborasi_id} ({row['nama']}) dibatalkan.")
    await sync_if_configured()


async def berkunjung_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Pakai: /berkunjung <kolaborasi_id>")
        return
    kolaborasi_id = int(args[0])
    row = await _require_status(update, kolaborasi_id, ["scheduled"])
    if not row:
        return
    await db.update_status(kolaborasi_id, "visited", update.effective_user.id)
    await update.message.reply_text(f"Kolaborasi #{kolaborasi_id} ({row['nama']}) ditandai Sudah Berkunjung.")
    await sync_if_configured()


async def upload_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Pakai: /upload <kolaborasi_id> <link_konten>")
        return
    kolaborasi_id = int(args[0])
    link = args[1]
    row = await _require_status(update, kolaborasi_id, ["visited"])
    if not row:
        return
    from datetime import date
    await db.update_status(
        kolaborasi_id, "content_uploaded", update.effective_user.id,
        link_konten=link, tanggal_upload=date.today(),
    )
    await update.message.reply_text(f"Kolaborasi #{kolaborasi_id} ({row['nama']}) ditandai Konten Sudah Upload.")
    await sync_if_configured()
