from datetime import datetime, timedelta
import zoneinfo
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import TIMEZONE_NAME
from database.queries import get_tickets_for_report
from services.report_service import build_daily_report

tz = zoneinfo.ZoneInfo(TIMEZONE_NAME)
router = Router()

class ReportStates(StatesGroup):
    waiting_for_custom_date = State()

def make_report_menu_keyboard(user_role: str = 'TEKNISI') -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="📅 Rekap Hari Ini (Semua)", callback_data="rekap:today:ALL"),
            InlineKeyboardButton(text="⏪ Rekap Kemarin (Semua)", callback_data="rekap:yesterday:ALL")
        ]
    ]

    if user_role in ('SUPERADMIN', 'SUPERVISOR'):
        buttons.append([
            InlineKeyboardButton(text="🟠 Rekap DELTA Hari Ini", callback_data="rekap:today:DELTA"),
            InlineKeyboardButton(text="🔵 Rekap INEO Hari Ini", callback_data="rekap:today:INEO")
        ])

    buttons.append([
        InlineKeyboardButton(text="🗓 Masukkan Tanggal Tertentu...", callback_data="rekap:custom:ALL")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(Command("rekap"))
@router.message(F.text == "📊 Rekap WhatsApp")
async def cmd_rekap(message: types.Message, current_user: dict | None = None):
    user_role = current_user.get('role', 'TEKNISI') if current_user else 'TEKNISI'

    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        date_str = args[1].strip()
        target_date = parse_user_date(date_str)
        if target_date:
            await send_rekap_for_date(message, target_date, vendor=None)
            return
        else:
            await message.answer(
                "⚠️ Format tanggal tidak dikenali. Gunakan format `DD/MM/YYYY` atau `YYYY-MM-DD`.\nContoh: `/rekap 21/10/2026`",
                parse_mode="Markdown"
            )
            return

    await message.answer(
        "📊 *PILIHAN REKAP HARIAN BROADBAND (FIBERSTAR)*\n\n"
        "Silakan pilih periode rekap yang ingin digenerate:",
        parse_mode="Markdown",
        reply_markup=make_report_menu_keyboard(user_role)
    )

def parse_user_date(text: str) -> datetime | None:
    text = text.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=tz)
        except ValueError:
            continue
    return None

@router.callback_query(F.data.startswith("rekap:"))
async def handle_rekap_callback(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    action = parts[1]
    vendor_filter = parts[2] if len(parts) > 2 else "ALL"
    target_vendor = None if vendor_filter == "ALL" else vendor_filter
    now = datetime.now(tz)

    if action == "today":
        await callback.answer("Menyiapkan rekap hari ini...")
        await send_rekap_for_date(callback, now, vendor=target_vendor)
    elif action == "yesterday":
        await callback.answer("Menyiapkan rekap kemarin...")
        yesterday = now - timedelta(days=1)
        await send_rekap_for_date(callback, yesterday, vendor=target_vendor)
    elif action == "custom":
        await state.set_state(ReportStates.waiting_for_custom_date)
        await callback.message.answer(
            "🗓 Silakan ketik tanggal rekap yang diinginkan (contoh: `20/10/2026` atau `2026-10-20`):",
            parse_mode="Markdown"
        )
        await callback.answer()

@router.message(ReportStates.waiting_for_custom_date)
async def handle_custom_date_input(message: types.Message, state: FSMContext):
    target_date = parse_user_date(message.text)
    if not target_date:
        await message.answer("⚠️ Tanggal tidak valid. Harap gunakan format `DD/MM/YYYY` (contoh: `20/10/2026`) atau `/cancel`.")
        return

    await state.clear()
    await send_rekap_for_date(message, target_date, vendor=None)

async def send_rekap_for_date(event: types.Message | types.CallbackQuery, target_date: datetime, vendor: str | None = None):
    target_str = target_date.strftime("%Y-%m-%d")
    tickets = await get_tickets_for_report(target_str, vendor=vendor)

    v_title = f" [{vendor}]" if vendor else ""
    if not tickets:
        msg = f"ℹ️ Tidak ada data tiket untuk tanggal rekap *{target_date.strftime('%d/%m/%Y')}*{v_title}."
        if isinstance(event, types.CallbackQuery):
            await event.message.answer(msg, parse_mode="Markdown")
        else:
            await event.answer(msg, parse_mode="Markdown")
        return

    chunks = build_daily_report(target_date, tickets, include_summary=True)

    for chunk in chunks:
        if isinstance(event, types.CallbackQuery):
            await event.message.answer(chunk)
        else:
            await event.answer(chunk)
