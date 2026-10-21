from datetime import datetime, timezone
import zoneinfo
from typing import List, Dict, Any, Tuple
from config import TIMEZONE_NAME
from services.sla_service import parse_iso_dt, format_duration

tz = zoneinfo.ZoneInfo(TIMEZONE_NAME)

def format_ticket_line(index: int, t: dict) -> str:
    ticket_no = t.get('ticket_no', '')
    cust_name = t.get('customer_name', '')
    crt = t.get('crt_number', '')

    # FU timestamp in DD/MM/YYYY HH:mm
    fu_dt = parse_iso_dt(t['fu_at'])
    fu_str = fu_dt.strftime("%d/%m/%Y %H:%M")

    # Warranty program tag (e.g. "Garansi delta")
    warranty = t.get('warranty_program')
    warranty_str = f" {warranty}" if warranty else ""

    status = t.get('status', 'OPEN')
    closing_note = t.get('closing_note')
    closed_at_str = t.get('closed_at')
    sla_result = t.get('sla_result')

    note_section = ""
    emoji_section = ""

    if status == 'CLOSED':
        emoji_section = " ✅"
        # Determine closed time HH:mm
        if closed_at_str:
            closed_dt = parse_iso_dt(closed_at_str)
            jam_tutup = closed_dt.strftime("%H:%M")
        else:
            jam_tutup = datetime.now(tz).strftime("%H:%M")

        # Check if in SLA or out SLA
        deadline_dt = parse_iso_dt(t['sla_deadline'])
        is_in_sla = (sla_result == 'IN_SLA') or (closed_at_str and parse_iso_dt(closed_at_str) <= deadline_dt)

        if is_in_sla:
            if closing_note and closing_note.strip() and closing_note.strip().lower() not in ('back to normal', 'ok', 'selesai'):
                note_section = f" (CLOSE WITH NOTE {closing_note.strip()} CLOSE IN SLA {jam_tutup})"
            else:
                note_section = f" (CLOSE IN SLA {jam_tutup})"
            emoji_section = " ✅"
        else:
            # Out of SLA
            overdue_sec = (parse_iso_dt(closed_at_str or datetime.now(timezone.utc).isoformat()) - deadline_dt).total_seconds()
            dur = format_duration(overdue_sec)
            note_section = f" (CLOSE OUT SLA {jam_tutup}, lewat {dur})"
            emoji_section = " ⚠️"

    elif status == 'CANCELLED':
        c_note = closing_note.strip() if closing_note else "Cancel Reschedule"
        note_section = f" ({c_note})"
        emoji_section = " ✅"

    elif status == 'MS_LOST':
        note_section = " ( MS LOST )"
        emoji_section = " ⚠️"

    elif status == 'PENDING':
        p_note = closing_note.strip() if closing_note else "Pelanggan Belum Ready"
        note_section = f" ({p_note})"
        emoji_section = " ⚠️"

    elif status in ('OPEN', 'ON_PROGRESS', 'RESCHEDULED'):
        note_section = ""
        emoji_section = ""

    # Line format: {no}. {ticket_no} {nama pelanggan} {CRT} {dd/mm/yyyy hh:mm} {tag garansi} ({catatan}) {emoji}
    # Clean redundant spaces
    line = f"{index}. {ticket_no} {cust_name} {crt} {fu_str}{warranty_str}{note_section}{emoji_section}".rstrip()
    return line

def build_daily_report(target_date: datetime, tickets: List[dict], include_summary: bool = True) -> List[str]:
    """
    Builds the report text and splits into messages <= 4096 characters if needed.
    """
    date_header_str = target_date.strftime("%d/%m/%y")
    header = f"List open tiket broadband {date_header_str}\n"

    lines = [header]
    total_count = len(tickets)
    closed_count = 0
    open_count = 0
    ms_lost_count = 0
    pending_count = 0
    cancelled_count = 0

    for idx, t in enumerate(tickets, start=1):
        line = format_ticket_line(idx, t)
        lines.append(line)

        st = t.get('status', 'OPEN')
        if st == 'CLOSED':
            closed_count += 1
        elif st == 'MS_LOST':
            ms_lost_count += 1
        elif st == 'PENDING':
            pending_count += 1
        elif st == 'CANCELLED':
            cancelled_count += 1
        else:
            open_count += 1

    if include_summary and total_count > 0:
        summary_lines = [
            "",
            "📊 *Ringkasan Tiket:*",
            f"• Total: {total_count}",
            f"• Closed: {closed_count}",
            f"• Masih Aktif (Open/Progress): {open_count}",
            f"• MS Lost: {ms_lost_count}",
            f"• Pending: {pending_count}",
            f"• Cancelled: {cancelled_count}"
        ]
        lines.extend(summary_lines)

    # Join and split if exceeds 4096 chars
    full_text = "\n".join(lines)
    if len(full_text) <= 4000:
        return [full_text]

    # Split into chunks cleanly at newlines
    chunks = []
    current_chunk = []
    current_len = 0

    for line in lines:
        if current_len + len(line) + 1 > 3900:
            chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_len = len(line) + 1
        else:
            current_chunk.append(line)
            current_len += len(line) + 1

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks
