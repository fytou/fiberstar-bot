import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from config import BOT_TOKEN
from database.db import init_db
from middlewares.auth import WhitelistMiddleware
from handlers import (
    common_router,
    ingest_router,
    tickets_router,
    status_flow_router,
    report_router,
    admin_router,
)
from scheduler.reminders import start_reminder_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("fiberstar-bot")

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not configured! Please provide BOT_TOKEN in .env file.")
        print("\n[PERINGATAN] BOT_TOKEN belum diisi di file .env!")
        print("Silakan edit file .env dan masukkan token bot dari @BotFather sebelum menjalankan bot.\n")
        return

    logger.info("Initializing database...")
    await init_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Register Middlewares
    whitelist_mw = WhitelistMiddleware()
    dp.message.middleware(whitelist_mw)
    dp.callback_query.middleware(whitelist_mw)

    # Register Handlers
    dp.include_router(common_router)
    dp.include_router(admin_router)
    dp.include_router(status_flow_router)
    dp.include_router(tickets_router)
    dp.include_router(report_router)
    dp.include_router(ingest_router)

    # Start SLA Reminders
    scheduler = start_reminder_scheduler(bot)

    # Register Bot Menu Commands in Telegram UI
    await bot.set_my_commands([
        BotCommand(command="start", description="🏠 Menu Utama"),
        BotCommand(command="open", description="📋 Antrian Tiket Aktif"),
        BotCommand(command="rekap", description="📊 Rekap Laporan WhatsApp"),
        BotCommand(command="cari", description="🔍 Cari Tiket (No Tiket/CRT/Nama)"),
        BotCommand(command="whitelist", description="👥 Kelola Whitelist User"),
        BotCommand(command="help", description="❓ Panduan Format & Alur"),
        BotCommand(command="me", description="👤 Profil Saya"),
        BotCommand(command="cancel", description="🚫 Batalkan Operasi")
    ])

    logger.info("Bot Fiberstar Pekanbaru is starting polling...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
