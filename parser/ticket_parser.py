import re
from datetime import datetime, timedelta, timezone
import zoneinfo
from typing import List, Dict, Any, Optional, Tuple
from config import TIMEZONE_NAME, SLA_HOURS

tz = zoneinfo.ZoneInfo(TIMEZONE_NAME)

class ParsedTicket:
    def __init__(self):
        self.raw_text: str = ""
        self.status_awal: Optional[str] = None
        self.region: Optional[str] = None
        self.ticket_no: Optional[str] = None
        self.partner_name: Optional[str] = None
        self.customer_name: Optional[str] = None
        self.address: Optional[str] = None
        self.crt_number: Optional[str] = None
        self.olt: Optional[str] = None
        self.pon: Optional[str] = None
        self.phone: Optional[str] = None
        self.issue_type: Optional[str] = None
        self.issue_detail: Optional[str] = None
        self.rx_power_dbm: Optional[float] = None
        self.reported_at: Optional[str] = None
        self.fu_at: Optional[datetime] = None
        self.warranty_program: Optional[str] = None
        self.vendor: str = "DELTA"
        self.status: str = "OPEN"
        self.closing_note: Optional[str] = None
        self.closed_at: Optional[str] = None
        self.sla_result: Optional[str] = None
        self.sla_deadline: Optional[datetime] = None
        self.missing_fields: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticket_no": self.ticket_no,
            "crt_number": self.crt_number,
            "customer_name": self.customer_name,
            "partner_name": self.partner_name,
            "address": self.address,
            "region": self.region,
            "olt": self.olt,
            "pon": self.pon,
            "phone": self.phone,
            "issue_type": self.issue_type,
            "issue_detail": self.issue_detail,
            "rx_power_dbm": self.rx_power_dbm,
            "warranty_program": self.warranty_program,
            "vendor": self.vendor,
            "status": self.status,
            "closing_note": self.closing_note,
            "reported_at": self.reported_at,
            "fu_at": self.fu_at.isoformat() if self.fu_at else None,
            "sla_deadline": self.sla_deadline.isoformat() if self.sla_deadline else None,
            "sla_result": self.sla_result,
            "closed_at": self.closed_at,
            "raw_text": self.raw_text,
            "missing_fields": self.missing_fields,
            "is_valid": len(self.missing_fields) == 0
        }

def normalize_phone(raw_phone: str) -> str:
    cleaned = re.sub(r'[^0-9+]', '', raw_phone.strip())
    if cleaned.startswith('+62'):
        return cleaned[1:]
    elif cleaned.startswith('62'):
        return cleaned
    elif cleaned.startswith('0'):
        return '62' + cleaned[1:]
    return cleaned

def parse_single_ticket_block(block: str, header_note: Optional[str] = None) -> ParsedTicket:
    pt = ParsedTicket()
    pt.raw_text = block.strip()
    if header_note and header_note.strip():
        pt.status_awal = header_note.strip()
        pt.status = "CLOSED"
        pt.closing_note = header_note.strip()
        pt.closed_at = datetime.now(timezone.utc).isoformat()

    lines = [line.strip() for line in block.splitlines() if line.strip()]

    # 1. Ticket Number: T\d{7}-\d{6}-\d{2}
    ticket_no_match = re.search(r'\b(T\d{7}-\d{6}-\d{2})\b', block, re.IGNORECASE)
    if ticket_no_match:
        pt.ticket_no = ticket_no_match.group(1).upper()
    else:
        # Fallback broader pattern if format varies slightly
        ticket_fallback = re.search(r'\b([A-Z]\d{6,8}-\d{6}-\d{2})\b', block, re.IGNORECASE)
        if ticket_fallback:
            pt.ticket_no = ticket_fallback.group(1).upper()

    # 2. Region: line right after [TSHOOT]
    tshoot_pos = -1
    for idx, l in enumerate(lines):
        if '[TSHOOT]' in l.upper():
            tshoot_pos = idx
            break
    
    if tshoot_pos != -1 and tshoot_pos + 1 < len(lines):
        next_line = lines[tshoot_pos + 1]
        # Make sure next line is not ticket_no or Dear Team
        if not re.search(r'^(T\d|Dear Team)', next_line, re.IGNORECASE):
            pt.region = next_line

    # 3. Customer name & partner name
    # Nama : <mitra> - <pelanggan>
    name_match = re.search(r'Nama\s*:\s*(.+)$', block, re.MULTILINE | re.IGNORECASE)
    if name_match:
        full_name_line = name_match.group(1).strip()
        if ' - ' in full_name_line:
            parts = full_name_line.split(' - ', 1)
            pt.partner_name = parts[0].strip()
            pt.customer_name = parts[1].strip()
        elif '-' in full_name_line:
            parts = full_name_line.split('-', 1)
            pt.partner_name = parts[0].strip()
            pt.customer_name = parts[1].strip()
        else:
            pt.partner_name = None
            pt.customer_name = full_name_line

    # 4. Address: from Alamat : ... to CRT : ...
    addr_match = re.search(r'Alamat\s*:\s*(.*?)(?=\n\s*CRT\s*:)', block, re.DOTALL | re.IGNORECASE)
    if addr_match:
        addr_clean = addr_match.group(1).strip()
        # Clean multi commas and duplicate spaces
        addr_clean = re.sub(r',\s*,+', ',', addr_clean)
        addr_clean = re.sub(r'\s+', ' ', addr_clean).strip()
        pt.address = addr_clean

    # 5. CRT Number
    crt_match = re.search(r'CRT\s*:\s*(CRT\d+)', block, re.IGNORECASE)
    if not crt_match:
        crt_match = re.search(r'\b(CRT\d+)\b', block, re.IGNORECASE)
    if crt_match:
        pt.crt_number = crt_match.group(1).upper()

    # 6. OLT & PON
    olt_match = re.search(r'OLT\s*:\s*(.+)$', block, re.MULTILINE | re.IGNORECASE)
    if olt_match:
        pt.olt = olt_match.group(1).strip()

    pon_match = re.search(r'PON\s*:\s*(.+)$', block, re.MULTILINE | re.IGNORECASE)
    if pon_match:
        pt.pon = pon_match.group(1).strip()

    # 7. Telp
    telp_match = re.search(r'Telp\s*:\s*(.+)$', block, re.MULTILINE | re.IGNORECASE)
    if telp_match:
        pt.phone = normalize_phone(telp_match.group(1).strip())

    # 8. Issue Type: first non-empty line after Telp
    telp_line_idx = -1
    for idx, l in enumerate(lines):
        if re.search(r'^Telp\s*:', l, re.IGNORECASE):
            telp_line_idx = idx
            break
    
    if telp_line_idx != -1 and telp_line_idx + 1 < len(lines):
        candidate_issue = lines[telp_line_idx + 1]
        # Ignore if it is already a timestamp or FU to FOP
        if not re.search(r'(FU to FOP|\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})', candidate_issue, re.IGNORECASE):
            pt.issue_type = candidate_issue
            # Check for rx power dBm
            rx_match = re.search(r'(-?\d+(?:\.\d+)?)\s*dBm', candidate_issue, re.IGNORECASE)
            if rx_match:
                try:
                    pt.rx_power_dbm = float(rx_match.group(1))
                except ValueError:
                    pass

    # 9. Reported At (ISO Timestamp with timezone)
    iso_match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2}))', block)
    if iso_match:
        pt.reported_at = iso_match.group(1)

    # 10. FU to FOP timestamp: <dd/mm/yyyy> <hh:mm> FU to FOP
    fu_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})\s*(\d{1,2}:\d{2})\s*FU to FOP', block, re.IGNORECASE)
    if fu_match:
        date_str = fu_match.group(1)
        time_str = fu_match.group(2)
        try:
            parsed_dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
            pt.fu_at = parsed_dt.replace(tzinfo=tz)
        except Exception:
            pass
    else:
        # Fallback: maybe date is on one line and hh:mm FU to FOP is on next line
        fu_split_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})\s*\n\s*(\d{1,2}:\d{2})\s*FU to FOP', block, re.IGNORECASE)
        if fu_split_match:
            date_str = fu_split_match.group(1)
            time_str = fu_split_match.group(2)
            try:
                parsed_dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
                pt.fu_at = parsed_dt.replace(tzinfo=tz)
            except Exception:
                pass

    # Fallback cascade for entry time: fu_at -> reported_at -> ticket_no date -> now
    if not pt.fu_at:
        if pt.reported_at:
            try:
                parsed_dt = datetime.fromisoformat(pt.reported_at)
                pt.fu_at = parsed_dt.astimezone(tz)
            except Exception:
                pass

    if not pt.fu_at and pt.ticket_no:
        # T0000001-201026-01 -> 20/10/26 -> 2026-10-20
        date_part_match = re.search(r'-(\d{2})(\d{2})(\d{2})-', pt.ticket_no)
        if date_part_match:
            d, m, y = date_part_match.groups()
            try:
                parsed_dt = datetime.strptime(f"{d}/{m}/20{y} 08:00", "%d/%m/%Y %H:%M")
                pt.fu_at = parsed_dt.replace(tzinfo=tz)
            except Exception:
                pass

    if not pt.fu_at:
        pt.fu_at = datetime.now(tz)

    # 11. Calculate SLA Deadline: fu_at + SLA_HOURS (24 hours)
    pt.sla_deadline = pt.fu_at + timedelta(hours=SLA_HOURS)

    # Check SLA result if status was CLOSED initially
    if pt.status == "CLOSED":
        now_dt = datetime.now(tz)
        if now_dt <= pt.sla_deadline:
            pt.sla_result = "IN_SLA"
        else:
            pt.sla_result = "OUT_SLA"

    # 12. Warranty program: Garansi Aktivasi DELTA / INEO
    warranty_match = re.search(r'Garansi\s+Aktivasi\s+(DELTA|INEO)', block, re.IGNORECASE)
    if warranty_match:
        prog = warranty_match.group(1).upper()
        pt.warranty_program = f"Garansi {prog.lower()}"
        pt.vendor = prog
    elif re.search(r'\bGaransi\s+(delta|ineo)\b', block, re.IGNORECASE):
        w_match = re.search(r'\bGaransi\s+(delta|ineo)\b', block, re.IGNORECASE)
        prog = w_match.group(1).upper()
        pt.warranty_program = f"Garansi {prog.lower()}"
        pt.vendor = prog
    elif 'ineo' in block.lower():
        pt.vendor = 'INEO'
    else:
        pt.vendor = 'DELTA'

    # 13. Validation of mandatory fields: ticket_no, crt_number, customer_name, issue_type
    if not pt.ticket_no:
        pt.missing_fields.append("Nomor Tiket (ticket_no)")
    if not pt.crt_number:
        pt.missing_fields.append("Nomor CRT (crt_number)")
    if not pt.customer_name:
        pt.missing_fields.append("Nama Pelanggan")
    if not pt.issue_type:
        pt.missing_fields.append("Jenis Kendala (issue_type)")

    return pt

def parse_tickets_from_message(message_text: str) -> List[ParsedTicket]:
    """
    Handles single or multiple tickets in one message.
    Tickets are divided by '====' or separate '[TSHOOT]' blocks.
    Preserves optional note written above [TSHOOT] as status_awal.
    """
    raw_blocks = []
    
    # Check if separated by ====
    if '====' in message_text:
        sections = [s for s in message_text.split('====') if s.strip()]
    else:
        # Split on [TSHOOT], but preserve text before the first [TSHOOT]
        tshoot_indices = [m.start() for m in re.finditer(r'\[TSHOOT\]', message_text, re.IGNORECASE)]
        if len(tshoot_indices) <= 1:
            sections = [message_text]
        else:
            sections = []
            # First section starts from 0 to 2nd tshoot, etc.
            # But let's check notes above each TSHOOT:
            for i in range(len(tshoot_indices)):
                start = 0 if i == 0 else tshoot_indices[i]
                # If there was a note right before this [TSHOOT], we should include it
                # For i > 0, find where the previous ticket ended
                end = tshoot_indices[i+1] if i + 1 < len(tshoot_indices) else len(message_text)
                sections.append(message_text[start:end])

    results: List[ParsedTicket] = []

    for section in sections:
        if not section.strip():
            continue
        
        # Check if there is header note before [TSHOOT]
        header_note = None
        tshoot_match = re.search(r'\[TSHOOT\]', section, re.IGNORECASE)
        ticket_body = section
        if tshoot_match:
            pre_tshoot = section[:tshoot_match.start()].strip()
            # If there's text before [TSHOOT], check if it's a technician note
            if pre_tshoot:
                header_note = pre_tshoot
            ticket_body = section[tshoot_match.start():]

        # Only process if looks like a ticket or has ticket_no/CRT
        if '[TSHOOT]' in section.upper() or 'CRT' in section.upper() or re.search(r'T\d{7}', section):
            parsed = parse_single_ticket_block(ticket_body, header_note=header_note)
            results.append(parsed)

    return results
