import logging
import asyncio
from datetime import datetime, timezone
from aiogram import Bot
from config import TIMEZONE_NAME
from database.queries import (
    get_pending_reminders,
    record_reminder_sent,
    get_team
)
from services.sla_service import parse_iso_dt, format_duration

logger = logging.getLogger(__name__)

async def check_and_send_sla_reminders(bot: Bot):
    try:
        team = await get_team()
        chat_id = team.get('report_chat_id') if team else None

        if not chat_id:
            # If no team group registered, skip sending to avoid errors
            return

        # 1. Check SLA 60 minutes
        pending_60 = await get_pending_reminders('SLA_60', minutes_before=60)
        for t in pending_60:
            now = datetime.now(timezone.utc)
            deadline = parse_iso_dt(t['sla_deadline'])
            diff = (deadline - now).total_seconds()
            dur = format_duration(diff)

            msg = (
                f"⏰ *PENGINGAT SLA (60 MENIT)*\n\n"
                f"Tiket `{t['ticket_no']}` akan melewati batas SLA dalam *{dur}*!\n"
                f"• Pelanggan: *{t['customer_name']}*\n"
                f"• CRT: `{t['crt_number']}`\n"
                f"• Status: *{t['status']}*\n\n"
                f"👉 Buka detail: `/detail_{t['ticket_id']}`"
            )
            try:
                await bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
                await record_reminder_sent(t['ticket_id'], 'SLA_60')
                logger.info(f"Sent SLA_60 reminder for ticket {t['ticket_no']}")
            except Exception as e:
                logger.error(f"Failed to send SLA_60 reminder for ticket {t['ticket_no']}: {e}")

        # 2. Check SLA 15 minutes
        pending_15 = await get_pending_reminders('SLA_15', minutes_before=15)
        for t in pending_15:
            now = datetime.now(timezone.utc)
            deadline = parse_iso_dt(t['sla_deadline'])
            diff = (deadline - now).total_seconds()
            dur = format_duration(diff)

            msg = (
                f"🚨 *PERINGATAN KRITIS: BATAS SLA 15 MENIT!*\n\n"
                f"Tiket `{t['ticket_no']}` tersisa waktu *{dur}* sebelum SLA terlampaui (OUT SLA)!\n"
                f"• Pelanggan: *{t['customer_name']}*\n"
                f"• CRT: `{t['crt_number']}`\n"
                f"• Status: *{t['status']}*\n\n"
                f"👉 Segera update status: `/detail_{t['ticket_id']}`"
            )
            try:
                await bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
                await record_reminder_sent(t['ticket_id'], 'SLA_15')
                logger.info(f"Sent SLA_15 reminder for ticket {t['ticket_no']}")
            except Exception as e:
                logger.error(f"Failed to send SLA_15 reminder for ticket {t['ticket_no']}: {e}")

    except Exception as e:
        logger.error(f"Error in check_and_send_sla_reminders: {e}", exc_info=True)

def start_reminder_scheduler(bot: Bot):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_and_send_sla_reminders,
        'interval',
        minutes=1,
        args=[bot],
        id='sla_reminders_job',
        replace_existing=True
    )
    scheduler.start()
    logger.info("SLA Reminder scheduler started (checks every 1 minute).")
    return scheduler
