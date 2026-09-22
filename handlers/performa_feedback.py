"""
/performa <kolaborasi_id> <views> <likes> <comments> [shares] [saves]
/lihat_performa <kolaborasi_id>
/feedback <kolaborasi_id> <teks feedback>
/lihat_feedback <kolaborasi_id>
"""
from telegram import Update
from telegram.ext import ContextTypes

import db
from utils.sheets_sync import sync_if_configured


async def performa_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "Pakai: /performa <kolaborasi_id> <views> <likes> <comments> [shares] [saves]"
        )
        return
    try:
        kolaborasi_id = int(args[0])
        views, likes, comments = int(args[1]), int(args[2]), int(args[3])
        shares = int(args[4]) if len(args) > 4 else None
        saves = int(args[5]) if len(args) > 5 else None
    except ValueError:
        await update.message.reply_text("Semua angka harus berupa bilangan bulat.")
        return

    row = await db.get_kolaborasi(kolaborasi_id)
    if not row:
        await update.message.reply_text(f"Kolaborasi #{kolaborasi_id} tidak ditemukan.")
        return
    if row["status"] not in ("content_uploaded", "performance_reviewed"):
        await update.message.reply_text(
            "Kolaborasi ini belum masuk status 'Konten Sudah Upload', pastikan sudah /upload dulu."
        )
        return

    await db.save_performa(kolaborasi_id, views, likes, comments, shares, saves, None, update.effective_user.id)
    if row["status"] != "performance_reviewed":
        await db.update_status(kolaborasi_id, "performance_reviewed", update.effective_user.id)
    await update.message.reply_text(
        f"Performa kolaborasi #{kolaborasi_id} ({row['nama']}) tersimpan: "
        f"views={views}, likes={likes}, comments={comments}, shares={shares or '-'}, saves={saves or '-'}."
    )
    await sync_if_configured()


async def lihat_performa_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Pakai: /lihat_performa <kolaborasi_id>")
        return
    kolaborasi_id = int(context.args[0])
    rows = await db.get_performa(kolaborasi_id)
    if not rows:
        await update.message.reply_text(f"Belum ada data performa untuk kolaborasi #{kolaborasi_id}.")
        return
    lines = [
        f"- {r['input_at']:%Y-%m-%d}: views={r['views']}, likes={r['likes']}, "
        f"comments={r['comments']}, shares={r['shares'] or '-'}, saves={r['saves'] or '-'}"
        for r in rows
    ]
    await update.message.reply_text(f"Performa kolaborasi #{kolaborasi_id}:\n" + "\n".join(lines))


async def feedback_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Pakai: /feedback <kolaborasi_id> <teks feedback>")
        return
    kolaborasi_id = int(args[0])
    teks = " ".join(args[1:])
    row = await db.get_kolaborasi(kolaborasi_id)
    if not row:
        await update.message.reply_text(f"Kolaborasi #{kolaborasi_id} tidak ditemukan.")
        return
    await db.save_feedback(kolaborasi_id, teks, update.effective_user.id)
    await update.message.reply_text(f"Feedback untuk kolaborasi #{kolaborasi_id} ({row['nama']}) tersimpan.")


async def lihat_feedback_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Pakai: /lihat_feedback <kolaborasi_id>")
        return
    kolaborasi_id = int(context.args[0])
    rows = await db.get_feedback(kolaborasi_id)
    if not rows:
        await update.message.reply_text(f"Belum ada feedback untuk kolaborasi #{kolaborasi_id}.")
        return
    lines = [f"- {r['input_at']:%Y-%m-%d}: {r['feedback_text']}" for r in rows]
    await update.message.reply_text(f"Feedback kolaborasi #{kolaborasi_id}:\n" + "\n".join(lines))
