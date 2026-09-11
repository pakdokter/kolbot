from telegram import Update
from telegram.ext import ContextTypes

import db
from config import STATUS_LABELS

PAGE_SIZE = 20


def _format_row(row) -> str:
    handle = row["tiktok_username"] or row["ig_username"] or "-"
    tanggal = f" | kunjungan: {row['tanggal_kunjungan']}" if row["tanggal_kunjungan"] else ""
    return f"#{row['id']} {row['nama']} (@{handle}){tanggal}"


async def _reply_list(update, rows, empty_msg, title):
    if not rows:
        await update.message.reply_text(empty_msg)
        return
    lines = [_format_row(r) for r in rows[:PAGE_SIZE]]
    text = f"{title} ({len(rows)}):\n" + "\n".join(lines)
    if len(rows) > PAGE_SIZE:
        text += f"\n... dan {len(rows) - PAGE_SIZE} lainnya."
    await update.message.reply_text(text)


async def list_kol_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await db.list_all_kolaborasi()
    await _reply_list(update, rows, "Belum ada KOL yang diinput.", "Semua KOL yang pernah di-approach")


async def belum_membalas_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await db.list_by_status("approached")
    await _reply_list(update, rows, "Tidak ada KOL yang menunggu balasan.", "Belum Membalas")


async def sudah_membalas_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await db.list_by_status("replied")
    await _reply_list(update, rows, "Tidak ada KOL di status ini.", "Sudah Membalas")


async def terjadwal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await db.list_by_status("scheduled")
    await _reply_list(update, rows, "Tidak ada KOL yang terjadwal.", "Terjadwal Kunjungan")


async def sudah_berkunjung_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await db.list_by_status("visited")
    await _reply_list(update, rows, "Tidak ada KOL di status ini.", "Sudah Berkunjung")


async def sudah_upload_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await db.list_by_status("content_uploaded")
    await _reply_list(update, rows, "Tidak ada KOL di status ini.", "Konten Sudah Upload")


async def tolak_batal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ditolak = await db.list_by_status("ditolak")
    batal = await db.list_by_status("batal")
    rows = list(ditolak) + list(batal)
    await _reply_list(update, rows, "Tidak ada KOL yang ditolak/batal.", "Ditolak / Batal")


async def detail_kol_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Pakai: /detail_kol <username atau nama>")
        return
    query = " ".join(context.args)
    kol = await db.find_kol_by_username(query)
    if not kol:
        await update.message.reply_text(f"KOL '{query}' tidak ditemukan.")
        return

    kolaborasi_list = await db.list_kolaborasi_by_kol(kol["id"])
    lines = [
        f"KOL #{kol['id']} — {kol['nama']}",
        f"TikTok: @{kol['tiktok_username'] or '-'} | IG: @{kol['ig_username'] or '-'}",
        f"Followers TikTok: {kol['followers_tiktok'] or '-'} | Followers IG: {kol['followers_ig'] or '-'}",
        f"Niche: {kol['niche'] or '-'} | Domisili: {kol['domisili'] or '-'}",
        f"Kontak: {kol['kontak'] or '-'}",
        f"Catatan: {kol['catatan'] or '-'}",
        "",
        f"Riwayat kolaborasi ({len(kolaborasi_list)}):",
    ]
    for k in kolaborasi_list:
        label = STATUS_LABELS.get(k["status"], k["status"])
        lines.append(f"  #{k['id']} [{label}] tipe: {k['tipe_kolaborasi'] or '-'} | pic: {k['pic'] or '-'}")
    await update.message.reply_text("\n".join(lines))
