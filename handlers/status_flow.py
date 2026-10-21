from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database.queries import (
    ALLOWED_TRANSITIONS,
    get_ticket_by_id,
    update_ticket_status
)
from services.reply_service import generate_closed_reply_text

router = Router()

class StatusFlowStates(StatesGroup):
    waiting_for_custom_note = State()
    waiting_for_reopen_reason = State()

def make_status_change_keyboard(ticket_id: int, current_status: str) -> InlineKeyboardMarkup:
    allowed = ALLOWED_TRANSITIONS.get(current_status, [])
    buttons = []

    status_labels = {
        'ON_PROGRESS': '▶️ Kerjakan (On Progress)',
        'PENDING': '⚠️ Pending',
        'MS_LOST': '⚠️ MS Lost',
        'RESCHEDULED': '🗓 Rescheduled',
        'CANCELLED': '🚫 Cancel',
        'CLOSED': '✅ Selesaikan (Closed)',
        'OPEN': '🔄 Buka Ulang (Reopen)'
    }

    row = []
    for target in allowed:
        label = status_labels.get(target, target)
        row.append(InlineKeyboardButton(text=label, callback_data=f"s:{ticket_id}:{target}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def make_quick_note_keyboard(ticket_id: int, to_status: str) -> InlineKeyboardMarkup:
    buttons = []
    if to_status == 'CLOSED':
        buttons.append([
            InlineKeyboardButton(text="⚡ Back To Normal", callback_data=f"sn:{ticket_id}:{to_status}:btn"),
            InlineKeyboardButton(text="⚡ OK / Selesai", callback_data=f"sn:{ticket_id}:{to_status}:ok")
        ])
    elif to_status == 'CANCELLED':
        buttons.append([
            InlineKeyboardButton(text="⚡ Cancel Reschedule", callback_data=f"sn:{ticket_id}:{to_status}:cr"),
            InlineKeyboardButton(text="⚡ Dibatalkan Pelanggan", callback_data=f"sn:{ticket_id}:{to_status}:dp")
        ])
    elif to_status in ('PENDING', 'MS_LOST'):
        buttons.append([
            InlineKeyboardButton(text="⚡ Pelanggan Belum Ready", callback_data=f"sn:{ticket_id}:{to_status}:pbr"),
            InlineKeyboardButton(text="⚡ Pelanggan Tidak di Lokasi", callback_data=f"sn:{ticket_id}:{to_status}:ptl")
        ])

    buttons.append([
        InlineKeyboardButton(text="✏️ Ketik Catatan Manual", callback_data=f"sn:{ticket_id}:{to_status}:custom"),
        InlineKeyboardButton(text="❌ Batal", callback_data=f"t:view:{ticket_id}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.callback_query(F.data.startswith("s:"))
async def handle_status_change_request(callback: types.CallbackQuery, state: FSMContext):
    # format: s:<ticket_id>:<to_status>
    parts = callback.data.split(":")
    ticket_id = int(parts[1])
    to_status = parts[2]

    ticket = await get_ticket_by_id(ticket_id)
    if not ticket:
        await callback.answer("Tiket tidak ditemukan.", show_alert=True)
        return

    # Check idempotent
    if ticket['status'] == to_status:
        await callback.answer(f"Tiket sudah berstatus {to_status}.", show_alert=True)
        return

    # If transitioning to CLOSED from CLOSED -> OPEN (reopen), mandatory reason
    if ticket['status'] == 'CLOSED' and to_status == 'OPEN':
        await state.update_data(ticket_id=ticket_id, to_status=to_status)
        await state.set_state(StatusFlowStates.waiting_for_reopen_reason)
        await callback.message.answer(
            f"⚠️ *Buka Ulang Tiket:* `{ticket['ticket_no']}`\n\n"
            f"Silakan ketikkan *alasan buka ulang* tiket:",
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    # If status requires note (PENDING, MS_LOST, CANCELLED, CLOSED)
    if to_status in ('PENDING', 'MS_LOST', 'CANCELLED', 'CLOSED'):
        await callback.message.edit_text(
            f"📝 *Pilih Catatan untuk Status {to_status} Tiket:* `{ticket['ticket_no']}`\n"
            f"Pilih catatan cepat di bawah atau ketik manual:",
            parse_mode="Markdown",
            reply_markup=make_quick_note_keyboard(ticket_id, to_status)
        )
        await callback.answer()
        return

    # Otherwise (e.g. ON_PROGRESS, RESCHEDULED), can update directly
    from database.queries import update_ticket_status
    user_id = callback.from_user.id
    success, msg, updated = await update_ticket_status(ticket_id, user_id, to_status, note=None)

    if success:
        await callback.message.edit_text(
            f"✅ *Status Tiket Berhasil Diperbarui!*\n\n"
            f"• *No Tiket:* `{updated['ticket_no']}`\n"
            f"• *Status Baru:* *{to_status}*\n"
            f"• *Pelanggan:* {updated['customer_name']}\n",
            parse_mode="Markdown",
            reply_markup=make_status_change_keyboard(ticket_id, to_status)
        )
        await callback.answer("Status berhasil diubah!")
    else:
        await callback.answer(msg, show_alert=True)

@router.callback_query(F.data.startswith("sn:"))
async def handle_status_note_selection(callback: types.CallbackQuery, state: FSMContext):
    # format: sn:<ticket_id>:<to_status>:<shortcut_code>
    parts = callback.data.split(":")
    ticket_id = int(parts[1])
    to_status = parts[2]
    code = parts[3]

    note_map = {
        'btn': 'Back To Normal',
        'ok': 'OK Selesai',
        'cr': 'Cancel Reschedule',
        'dp': 'Dibatalkan Pelanggan',
        'pbr': 'Pelanggan Belum Ready',
        'ptl': 'Pelanggan Tidak di Lokasi'
    }

    if code == 'custom':
        await state.update_data(ticket_id=ticket_id, to_status=to_status)
        await state.set_state(StatusFlowStates.waiting_for_custom_note)
        await callback.message.answer(
            f"✏️ Silakan ketikkan *catatan teknisi* untuk tiket ini:"
        )
        await callback.answer()
        return

    note = note_map.get(code, "Selesai")
    user_id = callback.from_user.id
    success, msg, updated = await update_ticket_status(ticket_id, user_id, to_status, note=note)

    if success:
        reply_extra = ""
        # FR-09: Generator teks balasan jika tiket CLOSED
        if to_status == 'CLOSED':
            reply_text = generate_closed_reply_text(note, updated.get('original_text'))
            reply_extra = (
                f"\n📋 *Teks Balasan Siap Salin ke Grup FS (WhatsApp):*\n"
                f"```text\n{reply_text}\n```\n"
                f"_(Salin blok teks di atas dan kirimkan ke grup Fiberstar)_"
            )

        await callback.message.edit_text(
            f"✅ *Tiket Berhasil Diselesaikan!*\n\n"
            f"• *No Tiket:* `{updated['ticket_no']}`\n"
            f"• *Status:* *{to_status}*\n"
            f"• *Catatan:* _{note}_\n"
            f"• *Hasil SLA:* `{updated.get('sla_result') or 'IN_SLA'}`\n"
            f"{reply_extra}",
            parse_mode="Markdown"
        )
        await callback.answer("Tiket berhasil diupdate!")
    else:
        await callback.answer(msg, show_alert=True)

@router.message(StatusFlowStates.waiting_for_custom_note)
async def handle_custom_note_input(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ticket_id = data['ticket_id']
    to_status = data['to_status']
    note = message.text.strip()
    await state.clear()

    user_id = message.from_user.id
    success, msg, updated = await update_ticket_status(ticket_id, user_id, to_status, note=note)

    if success:
        reply_extra = ""
        if to_status == 'CLOSED':
            reply_text = generate_closed_reply_text(note, updated.get('original_text'))
            reply_extra = (
                f"\n📋 *Teks Balasan Siap Salin ke Grup FS (WhatsApp):*\n"
                f"```text\n{reply_text}\n```\n"
                f"_(Salin blok teks di atas dan kirimkan ke grup Fiberstar)_"
            )

        await message.answer(
            f"✅ *Status Tiket Berhasil Diperbarui!*\n\n"
            f"• *No Tiket:* `{updated['ticket_no']}`\n"
            f"• *Status:* *{to_status}*\n"
            f"• *Catatan:* _{note}_\n"
            f"• *Hasil SLA:* `{updated.get('sla_result') or 'IN_SLA'}`\n"
            f"{reply_extra}",
            parse_mode="Markdown"
        )
    else:
        await message.answer(f"❌ Gagal memperbarui status: {msg}")

@router.message(StatusFlowStates.waiting_for_reopen_reason)
async def handle_reopen_reason_input(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ticket_id = data['ticket_id']
    reason = message.text.strip()
    await state.clear()

    user_id = message.from_user.id
    success, msg, updated = await update_ticket_status(ticket_id, user_id, 'OPEN', note=f"Buka Ulang: {reason}")

    if success:
        await message.answer(
            f"🔄 *Tiket Berhasil Dibuka Ulang!*\n\n"
            f"• *No Tiket:* `{updated['ticket_no']}`\n"
            f"• *Status:* *OPEN*\n"
            f"• *Alasan:* _{reason}_\n"
            f"Tiket kembali masuk ke antrian aktif `/open`.",
            parse_mode="Markdown"
        )
    else:
        await message.answer(f"❌ Gagal membuka ulang tiket: {msg}")
