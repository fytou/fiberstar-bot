import uuid
from datetime import datetime, timezone
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from parser.ticket_parser import parse_tickets_from_message, ParsedTicket
from database.queries import (
    save_raw_message,
    get_ticket_by_no,
    get_active_tickets_by_crt,
    insert_ticket,
    get_ticket_by_id
)
from services.sla_service import parse_iso_dt

router = Router()

# In-memory store for pending confirmation tickets (keyed by temp_id)
PENDING_TICKETS: dict[str, dict] = {}

class EditFieldStates(StatesGroup):
    waiting_for_field_value = State()

def make_confirmation_keyboard(temp_id: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="✅ Simpan Tiket", callback_data=f"ingest:save:{temp_id}"),
            InlineKeyboardButton(text="❌ Batal", callback_data=f"ingest:cancel:{temp_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(F.text.func(lambda text: bool(text and ('[TSHOOT]' in text.upper() or 'CRT' in text.upper()))))
async def handle_ticket_ingest(message: types.Message, current_user: dict, state: FSMContext):
    # Only Admin, Supervisor, or authorized roles can ingest tickets
    user_role = current_user.get('role', 'TEKNISI')
    if user_role not in ('ADMIN', 'SUPERVISOR', 'TEKNISI'):
        await message.answer("⚠️ Anda tidak memiliki izin untuk menginput tiket baru.")
        return

    text = message.text
    parsed_list = parse_tickets_from_message(text)

    if not parsed_list:
        await message.answer(
            "⚠️ Teks tidak dapat dikenali sebagai format tiket Fiberstar `[TSHOOT]`.\n"
            "Pastikan memuat format `[TSHOOT]`, `CRT`, dan informasi pelanggan."
        )
        return

    # Save raw message to database
    raw_status = "SUCCESS" if all(p.to_dict()['is_valid'] for p in parsed_list) else "PARTIAL"
    raw_id = await save_raw_message(
        user_id=current_user['user_id'],
        message_text=text,
        parse_status=raw_status
    )

    for parsed in parsed_list:
        p_dict = parsed.to_dict()

        # Check FR-03: Duplicate ticket_no
        if p_dict.get('ticket_no'):
            existing_ticket = await get_ticket_by_no(p_dict['ticket_no'])
            if existing_ticket:
                await message.answer(
                    f"⛔ *Tiket Duplikat Ditolak!*\n\n"
                    f"Nomor Tiket: `{existing_ticket['ticket_no']}` sudah terdaftar dalam sistem.\n"
                    f"• Status Saat Ini: *{existing_ticket['status']}*\n"
                    f"• Pelanggan: {existing_ticket['customer_name']}\n"
                    f"• CRT: `{existing_ticket['crt_number']}`\n"
                    f"• Waktu FU: {existing_ticket['fu_at']}",
                    parse_mode="Markdown"
                )
                continue

        # Check CRT active ticket warning (FR-03)
        crt_warning = ""
        if p_dict.get('crt_number'):
            active_crt_tickets = await get_active_tickets_by_crt(p_dict['crt_number'])
            if active_crt_tickets:
                active_nos = ", ".join([f"`{t['ticket_no']}` ({t['status']})" for t in active_crt_tickets])
                crt_warning = f"\n⚠️ *Perhatian:* CRT `{p_dict['crt_number']}` masih memiliki tiket aktif: {active_nos}\n"

        # Check FR-02: Missing mandatory fields
        if not p_dict['is_valid']:
            missing_str = ", ".join(p_dict['missing_fields'])
            await message.answer(
                f"⚠️ *Tiket Gagal Terbaca Lengkap*\n\n"
                f"Field wajib yang belum terbaca:\n"
                f"🔴 *{missing_str}*\n\n"
                f"Silakan periksa format teks tiket dan kirim ulang.",
                parse_mode="Markdown"
            )
            continue

        # Format Summary (FR-02)
        temp_id = str(uuid.uuid4())[:8]
        p_dict['raw_id'] = raw_id
        PENDING_TICKETS[temp_id] = p_dict

        fu_display = parse_iso_dt(p_dict['fu_at']).strftime("%d/%m/%Y %H:%M")
        sla_display = parse_iso_dt(p_dict['sla_deadline']).strftime("%d/%m/%Y %H:%M")

        status_info = f"*{p_dict['status']}*"
        if p_dict.get('closing_note'):
            status_info += f" (Catatan Awal: _{p_dict['closing_note']}_)"

        summary_msg = (
            f"📋 *Konfirmasi Tiket Masuk (Pekanbaru)*\n"
            f"{crt_warning}\n"
            f"• *No Tiket:* `{p_dict['ticket_no']}`\n"
            f"• *CRT:* `{p_dict['crt_number']}`\n"
            f"• *Pelanggan:* {p_dict['customer_name']}\n"
            f"• *Mitra:* {p_dict.get('partner_name') or '-'}\n"
            f"• *Alamat:* {p_dict.get('address') or '-'}\n"
            f"• *OLT / PON:* {p_dict.get('olt') or '-'} / {p_dict.get('pon') or '-'}\n"
            f"• *Telepon:* `{p_dict.get('phone') or '-'}`\n"
            f"• *Kendala:* {p_dict['issue_type']}\n"
            f"• *Program:* {p_dict.get('warranty_program') or 'Reguler'}\n"
            f"• *Waktu FU:* {fu_display}\n"
            f"• *Batas SLA (24 Jam):* {sla_display}\n"
            f"• *Status Disimpan:* {status_info}\n\n"
            f"Apakah data tiket di atas sudah sesuai?"
        )

        await message.answer(
            summary_msg,
            parse_mode="Markdown",
            reply_markup=make_confirmation_keyboard(temp_id)
        )

@router.callback_query(F.data.startswith("ingest:"))
async def handle_ingest_callback(callback: types.CallbackQuery, current_user: dict):
    parts = callback.data.split(":")
    action = parts[1]
    temp_id = parts[2]

    if temp_id not in PENDING_TICKETS:
        await callback.answer("Data sesi tiket ini sudah kadaluarsa atau sudah disimpan.", show_alert=True)
        return

    ticket_data = PENDING_TICKETS[temp_id]

    if action == "save":
        # Check duplicate again just in case
        existing = await get_ticket_by_no(ticket_data['ticket_no'])
        if existing:
            del PENDING_TICKETS[temp_id]
            await callback.message.edit_text(f"⛔ Tiket `{ticket_data['ticket_no']}` sudah disimpan sebelumnya.")
            return

        inserted = await insert_ticket(
            user_id=current_user['user_id'],
            ticket_data=ticket_data,
            raw_id=ticket_data.get('raw_id')
        )
        del PENDING_TICKETS[temp_id]

        status_emoji = "✅" if inserted['status'] == 'CLOSED' else "🆕"
        await callback.message.edit_text(
            f"{status_emoji} *Tiket Berhasil Disimpan!*\n\n"
            f"• *No Tiket:* `{inserted['ticket_no']}`\n"
            f"• *Status:* *{inserted['status']}*\n"
            f"• *Pelanggan:* {inserted['customer_name']}\n"
            f"• *CRT:* `{inserted['crt_number']}`\n\n"
            f"Tiket kini sudah masuk ke antrian `/open` dan dapat dipantau oleh seluruh tim.",
            parse_mode="Markdown"
        )
        await callback.answer("Tiket berhasil disimpan!")

    elif action == "cancel":
        del PENDING_TICKETS[temp_id]
        await callback.message.edit_text(f"❌ Input tiket `{ticket_data['ticket_no']}` telah dibatalkan.")
        await callback.answer("Dibatalkan.")
