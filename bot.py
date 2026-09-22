import logging

from telegram import BotCommand
from telegram.ext import Application, CommandHandler

import db
from config import TELEGRAM_BOT_TOKEN
from handlers.input_kol import build_conversation_handler
from handlers import status, lists, performa_feedback
from utils import sheets_sync

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start_cmd(update, context):
    await update.message.reply_text(
        "Bot Manajemen KOL Stoa Space\n\n"
        "/input_kol - input KOL baru (upload screenshot lalu isi data)\n"
        "/reply <id> - tandai KOL sudah membalas\n"
        "/jadwal <id> <YYYY-MM-DD> - tandai jadwal kunjungan\n"
        "/reschedule <id> <YYYY-MM-DD> [alasan] - ubah jadwal\n"
        "/tolak <id> [alasan] - tandai ditolak\n"
        "/batalkan <id> [alasan] - batalkan jadwal\n"
        "/berkunjung <id> - tandai sudah berkunjung\n"
        "/upload <id> <link> - tandai konten sudah upload\n"
        "/performa <id> <views> <likes> <comments> [shares] [saves] - input performa\n"
        "/lihat_performa <id>\n"
        "/feedback <id> <teks>\n"
        "/lihat_feedback <id>\n"
        "/list_kol - semua KOL\n"
        "/belum_membalas\n"
        "/sudah_membalas\n"
        "/terjadwal\n"
        "/sudah_berkunjung\n"
        "/sudah_upload\n"
        "/tolak_batal\n"
        "/detail_kol <username/nama>\n"
        "/sync_sheets - sinkronkan ulang ke Google Sheets secara manual "
        "(data otomatis ke-sync tiap ada perubahan kalau sudah dikonfigurasi)"
    )


async def sync_sheets_cmd(update, context):
    if not sheets_sync.is_configured():
        await update.message.reply_text(
            "Sinkronisasi Google Sheets belum dikonfigurasi. "
            "Set GOOGLE_SHEETS_CREDENTIALS_JSON dan GOOGLE_SHEETS_SPREADSHEET_ID dulu."
        )
        return
    await update.message.reply_text("Sinkronisasi ke Google Sheets...")
    try:
        count = await sheets_sync.sync_all()
        await update.message.reply_text(f"Selesai, {count} baris kolaborasi disinkronkan.")
    except Exception:
        logger.exception("Sync sheets gagal")
        await update.message.reply_text("Sinkronisasi gagal, cek log untuk detail.")


async def post_init(application: Application):
    await db.init_db()
    await application.bot.set_my_commands([
        BotCommand("input_kol", "Input KOL baru"),
        BotCommand("list_kol", "Semua KOL"),
        BotCommand("belum_membalas", "KOL belum membalas"),
        BotCommand("sudah_membalas", "KOL sudah membalas"),
        BotCommand("terjadwal", "KOL terjadwal kunjungan"),
        BotCommand("sudah_berkunjung", "KOL sudah berkunjung"),
        BotCommand("sudah_upload", "Konten sudah upload"),
        BotCommand("tolak_batal", "KOL ditolak/batal"),
        BotCommand("detail_kol", "Detail satu KOL"),
        BotCommand("sync_sheets", "Sinkronkan ke Google Sheets"),
    ])
    logger.info("Database siap, bot commands terpasang.")


def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(build_conversation_handler())

    application.add_handler(CommandHandler("reply", status.reply_cmd))
    application.add_handler(CommandHandler("jadwal", status.jadwal_cmd))
    application.add_handler(CommandHandler("reschedule", status.reschedule_cmd))
    application.add_handler(CommandHandler("tolak", status.tolak_cmd))
    application.add_handler(CommandHandler("batalkan", status.batalkan_cmd))
    application.add_handler(CommandHandler("berkunjung", status.berkunjung_cmd))
    application.add_handler(CommandHandler("upload", status.upload_cmd))

    application.add_handler(CommandHandler("performa", performa_feedback.performa_cmd))
    application.add_handler(CommandHandler("lihat_performa", performa_feedback.lihat_performa_cmd))
    application.add_handler(CommandHandler("feedback", performa_feedback.feedback_cmd))
    application.add_handler(CommandHandler("lihat_feedback", performa_feedback.lihat_feedback_cmd))

    application.add_handler(CommandHandler("list_kol", lists.list_kol_cmd))
    application.add_handler(CommandHandler("belum_membalas", lists.belum_membalas_cmd))
    application.add_handler(CommandHandler("sudah_membalas", lists.sudah_membalas_cmd))
    application.add_handler(CommandHandler("terjadwal", lists.terjadwal_cmd))
    application.add_handler(CommandHandler("sudah_berkunjung", lists.sudah_berkunjung_cmd))
    application.add_handler(CommandHandler("sudah_upload", lists.sudah_upload_cmd))
    application.add_handler(CommandHandler("tolak_batal", lists.tolak_batal_cmd))
    application.add_handler(CommandHandler("detail_kol", lists.detail_kol_cmd))

    application.add_handler(CommandHandler("sync_sheets", sync_sheets_cmd))

    application.run_polling()


if __name__ == "__main__":
    main()
