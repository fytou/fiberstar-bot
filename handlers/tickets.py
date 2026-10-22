from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database.queries import (
    get_open_tickets,
    get_ticket_by_id,
    get_ticket_by_no,
    get_ticket_events,
    search_tickets
)
from services.sla_service import get_sla_status, parse_iso_dt

router = Router()

def make_open_list_keyboard(tickets: list[dict], user_role: str = 'TEKNISI') -> InlineKeyboardMarkup:
    buttons = []
    # Maximum 8 tickets per page
    for t in tickets[:8]:
        t_id = t['ticket_id']
        t_no = t['ticket_no']
        badge, _, _ = get_sla_status(t['sla_deadline'])
        emoji_dot = badge.split()[0]
        v_tag = f"[{t.get('vendor', 'DELTA')}] " if user_role in ('SUPERADMIN', 'SUPERVISOR') else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"{emoji_dot} {v_tag}{t_no} - {t['customer_name'][:16]}",
                callback_data=f"t:view:{t_id}"
            )
        ])

    # Filter buttons for Superadmin & Supervisor
    if user_role in ('SUPERADMIN', 'SUPERVISOR'):
        buttons.append([
            InlineKeyboardButton(text="🔘 Semua", callback_data="filter_open:ALL"),
            InlineKeyboardButton(text="🟠 DELTA", callback_data="filter_open:DELTA"),
            InlineKeyboardButton(text="🔵 INEO", callback_data="filter_open:INEO")
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(Command("open"))
@router.message(F.text == "📋 Antrian Tiket")
async def cmd_open(message: types.Message, current_user: dict):
    await show_open_tickets(message, current_user)

async def show_open_tickets(event: types.Message | types.CallbackQuery, current_user: dict, vendor_filter: str | None = None):
    user_role = current_user.get('role', 'TEKNISI')
    user_vendor = current_user.get('vendor', 'ALL')

    if vendor_filter:
        effective_vendor = vendor_filter if vendor_filter != 'ALL' else None
    elif user_role == 'TEKNISI':
        effective_vendor = user_vendor if user_vendor in ('DELTA', 'INEO') else None
    else:
        effective_vendor = None

    active_tickets = await get_open_tickets(vendor=effective_vendor)

    vendor_title = f" ({effective_vendor})" if effective_vendor else ""
    if not active_tickets:
        empty_msg = f"🎉 *Tidak ada antrian tiket aktif{vendor_title}!* \nSemua tiket telah diselesaikan atau dialihkan."
        if isinstance(event, types.CallbackQuery):
            await event.message.edit_text(empty_msg, parse_mode="Markdown")
        else:
            await event.answer(empty_msg, parse_mode="Markdown")
        return

    total = len(active_tickets)
    lines = [f"📋 *ANTRIAN TIKET AKTIF TIM PEKANBARU{vendor_title}* ({total} Tiket)\n_Diurutkan dari sisa SLA paling mendesak_\n"]

    for idx, t in enumerate(active_tickets, start=1):
        badge, label, urgency = get_sla_status(t['sla_deadline'])
        fu_dt = parse_iso_dt(t['fu_at']).strftime("%d/%m %H:%M")
        garansi = f" [{t['warranty_program']}]" if t.get('warranty_program') else ""
        v_label = f"[{t.get('vendor', 'DELTA')}]"

        operan_tag = ""
        if t.get('transferred_from'):
            operan_tag = f"\n   🚨 *[OPERAN DARI {t['transferred_from']}: {t.get('transfer_reason') or 'ODP Lost'}]*"

        lines.append(
            f"*{idx}.* `{t['ticket_no']}` — *{v_label}* {t['customer_name']}{garansi}{operan_tag}\n"
            f"   • CRT: `{t['crt_number']}` | Status: *{t['status']}*\n"
            f"   • Kendala: {t['issue_type']}\n"
            f"   • FU: {fu_dt} | SLA: {badge} ({label})\n"
            f"   👉 Ketik `/detail_{t['ticket_id']}` untuk kelola\n"
        )

    response_text = "\n".join(lines)
    if len(response_text) > 4000:
        response_text = response_text[:3900] + "\n\n...(Daftar tiket dipersingkat)..."

    kb = make_open_list_keyboard(active_tickets, user_role=user_role)
    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(response_text, parse_mode="Markdown", reply_markup=kb)
    else:
        await event.answer(response_text, parse_mode="Markdown", reply_markup=kb)

@router.callback_query(F.data.startswith("filter_open:"))
async def handle_filter_open(callback: types.CallbackQuery, current_user: dict):
    v = callback.data.split(":")[1]
    await show_open_tickets(callback, current_user, vendor_filter=v)
    await callback.answer(f"Filter vendor: {v}")

@router.message(Command("cari"))
async def cmd_search(message: types.Message, current_user: dict):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("ℹ️ *Gunakan format:* `/cari <nomor_tiket / nomor_crt / nama_pelanggan>`", parse_mode="Markdown")
        return

    query = args[1].strip()
    user_role = current_user.get('role', 'TEKNISI')
    user_vendor = current_user.get('vendor', 'ALL') if user_role == 'TEKNISI' else None

    results = await search_tickets(query, vendor=user_vendor)

    if not results:
        await message.answer(f"🔍 Tidak ditemukan tiket dengan kata kunci: *{query}*", parse_mode="Markdown")
        return

    lines = [f"🔍 *HASIL PENCARIAN:* `{query}` ({len(results)} tiket)\n"]
    buttons = []
    for t in results:
        badge, label, _ = get_sla_status(t['sla_deadline'])
        v_tag = f"[{t.get('vendor', 'DELTA')}]"
        lines.append(
            f"• `{t['ticket_no']}` {v_tag} ({t['status']})\n"
            f"  Pelanggan: {t['customer_name']} | CRT: `{t['crt_number']}`\n"
        )
        buttons.append([
            InlineKeyboardButton(text=f"Lihat {t['ticket_no']}", callback_data=f"t:view:{t['ticket_id']}")
        ])

    await message.answer("\n".join(lines), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.message(F.text == "🔍 Cari Tiket")
async def cmd_search_prompt(message: types.Message):
    await message.answer(
        "🔍 *Pencarian Tiket:*\n"
        "Silakan ketik perintah pencarian:\n"
        "`/cari <nomor_tiket / nomor_crt / nama_pelanggan>`\n\n"
        "Contoh: `/cari CRT1000` atau `/cari Budi`",
        parse_mode="Markdown"
    )

@router.message(F.text.regexp(r"^/detail_(\d+)$"))
async def cmd_detail_shortcut(message: types.Message, current_user: dict):
    match = message.text.strip().split("_")
    if len(match) == 2 and match[1].isdigit():
        ticket_id = int(match[1])
        await send_ticket_detail(message, ticket_id, current_user)

@router.callback_query(F.data.startswith("t:view:"))
async def handle_view_ticket_callback(callback: types.CallbackQuery, current_user: dict):
    ticket_id = int(callback.data.split(":")[2])
    await send_ticket_detail(callback, ticket_id, current_user)
    await callback.answer()

async def send_ticket_detail(event: types.Message | types.CallbackQuery, ticket_id: int, current_user: dict):
    ticket = await get_ticket_by_id(ticket_id)
    if not ticket:
        msg = "Tiket tidak ditemukan."
        if isinstance(event, types.CallbackQuery):
            await event.message.answer(msg)
        else:
            await event.answer(msg)
        return

    events = await get_ticket_events(ticket_id)

    badge, label, _ = get_sla_status(ticket['sla_deadline'])
    fu_str = parse_iso_dt(ticket['fu_at']).strftime("%d/%m/%Y %H:%M")
    sla_str = parse_iso_dt(ticket['sla_deadline']).strftime("%d/%m/%Y %H:%M")
    closed_str = parse_iso_dt(ticket['closed_at']).strftime("%d/%m/%Y %H:%M") if ticket.get('closed_at') else "-"

    timeline_lines = []
    for ev in events:
        ev_time = parse_iso_dt(ev['created_at']).strftime("%d/%m %H:%M")
        user_name = ev.get('full_name') or f"User {ev.get('user_id')}"
        from_st = ev.get('from_status') or "Baru"
        note = f" — _{ev['note']}_" if ev.get('note') else ""
        timeline_lines.append(f"• `{ev_time}` [{from_st} ➡️ *{ev['to_status']}*] oleh {user_name}{note}")

    timeline_text = "\n".join(timeline_lines) if timeline_lines else "Belum ada riwayat perubahan."

    status_badge = "✅" if ticket['status'] in ('CLOSED', 'CANCELLED') else "⏳"
    vendor_badge = "🟠 DELTA" if ticket.get('vendor') == 'DELTA' else "🔵 INEO"

    operan_info = ""
    if ticket.get('transferred_from'):
        operan_info = f"\n🚨 *STATUS OPERAN:* Dialihkan dari *{ticket['transferred_from']}* (Alasan: _{ticket.get('transfer_reason') or 'ODP Lost'}_)\n"

    detail_msg = (
        f"{status_badge} *DETAIL TIKET:* `{ticket['ticket_no']}`\n"
        f"🏷 *Vendor Penanggung Jawab:* *{vendor_badge}*{operan_info}\n\n"
        f"👤 *Pelanggan:* {ticket['customer_name']}\n"
        f"🏢 *Mitra:* {ticket.get('partner_name') or '-'}\n"
        f"📍 *Alamat:* {ticket.get('address') or '-'}\n"
        f"📞 *Telepon:* `{ticket.get('phone') or '-'}`\n"
        f"🌐 *OLT / PON:* `{ticket.get('olt') or '-'}` / `{ticket.get('pon') or '-'}`\n"
        f"🏷 *CRT:* `{ticket['crt_number']}`\n"
        f"⚠️ *Kendala:* {ticket['issue_type']}\n"
        f"🏷 *Program:* {ticket.get('warranty_program') or 'Reguler'}\n\n"
        f"⏱ *Waktu & SLA:*\n"
        f"• Waktu FU: `{fu_str}`\n"
        f"• Batas SLA: `{sla_str}` ({badge})\n"
        f"• Status Saat Ini: *{ticket['status']}*\n"
    )

    if ticket.get('closing_note'):
        detail_msg += f"• Catatan: _{ticket['closing_note']}_\n"
    if ticket['status'] == 'CLOSED':
        detail_msg += f"• Waktu Selesai: `{closed_str}` ({ticket.get('sla_result') or 'IN_SLA'})\n"

    detail_msg += f"\n📜 *Riwayat Tiket:*\n{timeline_text}"

    from handlers.status_flow import make_status_change_keyboard
    action_kb = make_status_change_keyboard(
        ticket['ticket_id'],
        ticket['status'],
        ticket_vendor=ticket.get('vendor', 'DELTA'),
        user_role=current_user.get('role', 'TEKNISI')
    )

    if isinstance(event, types.CallbackQuery):
        await event.message.answer(detail_msg, parse_mode="Markdown", reply_markup=action_kb)
    else:
        await event.answer(detail_msg, parse_mode="Markdown", reply_markup=action_kb)
