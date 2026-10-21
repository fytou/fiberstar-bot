from datetime import datetime, timezone
import zoneinfo
from typing import Optional, List, Dict, Any
from .db import get_db
from config import TIMEZONE_NAME

tz = zoneinfo.ZoneInfo(TIMEZONE_NAME)

ALLOWED_TRANSITIONS = {
    'OPEN': ['ON_PROGRESS', 'PENDING', 'MS_LOST', 'CANCELLED', 'CLOSED'],
    'ON_PROGRESS': ['PENDING', 'MS_LOST', 'CLOSED'],
    'PENDING': ['RESCHEDULED', 'CANCELLED', 'CLOSED'],
    'MS_LOST': ['RESCHEDULED', 'CANCELLED', 'CLOSED'],
    'RESCHEDULED': ['OPEN'],
    'CLOSED': ['OPEN']
}

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def now_local() -> datetime:
    return datetime.now(tz)

# --- USER & AUTH QUERIES ---

async def get_user(user_id: int) -> Optional[dict]:
    async with get_db() as conn:
        cur = await conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None

async def upsert_user(user_id: int, username: str, full_name: str, role: str = 'TEKNISI', is_active: int = 1, team_name: str = 'Pekanbaru') -> dict:
    async with get_db() as conn:
        cur = await conn.execute("SELECT team_id FROM teams WHERE name = ?", (team_name,))
        team_row = await cur.fetchone()
        team_id = team_row['team_id'] if team_row else 1

        cur = await conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        existing = await cur.fetchone()
        if existing:
            await conn.execute(
                "UPDATE users SET username = ?, full_name = ?, role = ?, is_active = ? WHERE user_id = ?",
                (username, full_name, role, is_active, user_id)
            )
        else:
            await conn.execute(
                "INSERT INTO users (user_id, team_id, username, full_name, role, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, team_id, username, full_name, role, is_active)
            )
        await conn.commit()
        return await get_user(user_id)

async def set_user_active(user_id: int, is_active: bool) -> bool:
    async with get_db() as conn:
        cur = await conn.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (1 if is_active else 0, user_id))
        await conn.commit()
        return cur.rowcount > 0

async def list_users() -> List[dict]:
    async with get_db() as conn:
        cur = await conn.execute("SELECT * FROM users ORDER BY role, full_name")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def get_team() -> Optional[dict]:
    async with get_db() as conn:
        cur = await conn.execute("SELECT * FROM teams LIMIT 1")
        row = await cur.fetchone()
        return dict(row) if row else None

async def set_report_chat_id(chat_id: int):
    async with get_db() as conn:
        await conn.execute("UPDATE teams SET report_chat_id = ? WHERE team_id = (SELECT team_id FROM teams LIMIT 1)", (chat_id,))
        await conn.commit()

# --- TICKET INGESTION QUERIES ---

async def get_ticket_by_no(ticket_no: str) -> Optional[dict]:
    async with get_db() as conn:
        cur = await conn.execute(
            """
            SELECT t.*, c.name as customer_name, c.partner_name, c.address, c.phone,
                   n.region, n.olt, n.pon, rm.message_text as original_text
            FROM tickets t
            JOIN customers c ON t.customer_id = c.customer_id
            JOIN network_nodes n ON t.node_id = n.node_id
            LEFT JOIN raw_messages rm ON t.raw_id = rm.raw_id
            WHERE t.ticket_no = ?
            """,
            (ticket_no,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None

async def get_active_tickets_by_crt(crt_number: str) -> List[dict]:
    async with get_db() as conn:
        cur = await conn.execute(
            """
            SELECT ticket_id, ticket_no, crt_number, status, fu_at, sla_deadline
            FROM tickets
            WHERE crt_number = ? AND status NOT IN ('CLOSED', 'CANCELLED')
            """,
            (crt_number,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def save_raw_message(user_id: int, message_text: str, parse_status: str) -> int:
    async with get_db() as conn:
        cur = await conn.execute(
            "INSERT INTO raw_messages (user_id, message_text, parse_status) VALUES (?, ?, ?)",
            (user_id, message_text, parse_status)
        )
        await conn.commit()
        return cur.lastrowid

async def insert_ticket(
    user_id: int,
    ticket_data: dict,
    raw_id: Optional[int] = None
) -> dict:
    """
    Inserts customer, network_node, ticket, and initial ticket_event.
    """
    async with get_db() as conn:
        # Team ID
        cur = await conn.execute("SELECT team_id FROM teams LIMIT 1")
        team_row = await cur.fetchone()
        team_id = team_row['team_id'] if team_row else 1

        # Customer
        cur = await conn.execute(
            "INSERT INTO customers (partner_name, name, address, phone) VALUES (?, ?, ?, ?)",
            (ticket_data.get('partner_name'), ticket_data['customer_name'], ticket_data.get('address'), ticket_data.get('phone'))
        )
        customer_id = cur.lastrowid

        # Network Node
        cur = await conn.execute(
            "INSERT INTO network_nodes (region, olt, pon, team_id) VALUES (?, ?, ?, ?)",
            (ticket_data.get('region'), ticket_data.get('olt'), ticket_data.get('pon'), team_id)
        )
        node_id = cur.lastrowid

        status = ticket_data.get('status', 'OPEN')
        fu_at = ticket_data['fu_at'] # ISO format string or datetime
        sla_deadline = ticket_data['sla_deadline'] # ISO format string or datetime
        closing_note = ticket_data.get('closing_note')
        closed_at = ticket_data.get('closed_at')
        sla_result = ticket_data.get('sla_result')

        # Insert Ticket
        cur = await conn.execute(
            """
            INSERT INTO tickets (
                ticket_no, crt_number, customer_id, node_id, raw_id,
                issue_type, issue_detail, rx_power_dbm, warranty_program,
                status, reported_at, fu_at, sla_deadline, sla_result,
                closed_at, closing_note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticket_data['ticket_no'],
                ticket_data['crt_number'],
                customer_id,
                node_id,
                raw_id,
                ticket_data['issue_type'],
                ticket_data.get('issue_detail'),
                ticket_data.get('rx_power_dbm'),
                ticket_data.get('warranty_program'),
                status,
                ticket_data.get('reported_at'),
                str(fu_at),
                str(sla_deadline),
                sla_result,
                str(closed_at) if closed_at else None,
                closing_note
            )
        )
        ticket_id = cur.lastrowid

        # Insert Initial Ticket Event
        await conn.execute(
            """
            INSERT INTO ticket_events (ticket_id, user_id, from_status, to_status, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ticket_id, user_id, None, status, closing_note or "Tiket diinput")
        )

        await conn.commit()
        return await get_ticket_by_id(ticket_id)

async def get_ticket_by_id(ticket_id: int) -> Optional[dict]:
    async with get_db() as conn:
        cur = await conn.execute(
            """
            SELECT t.*, c.name as customer_name, c.partner_name, c.address, c.phone,
                   n.region, n.olt, n.pon, rm.message_text as original_text
            FROM tickets t
            JOIN customers c ON t.customer_id = c.customer_id
            JOIN network_nodes n ON t.node_id = n.node_id
            LEFT JOIN raw_messages rm ON t.raw_id = rm.raw_id
            WHERE t.ticket_id = ?
            """,
            (ticket_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None

# --- STATUS FLOW & EVENTS ---

async def update_ticket_status(
    ticket_id: int,
    user_id: int,
    to_status: str,
    note: Optional[str] = None
) -> tuple[bool, str, Optional[dict]]:
    """
    Validates and updates ticket status, logs event, and calculates SLA if closing.
    Returns (success, message, updated_ticket).
    """
    async with get_db() as conn:
        cur = await conn.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,))
        ticket = await cur.fetchone()
        if not ticket:
            return False, "Tiket tidak ditemukan.", None

        current_status = ticket['status']
        if current_status == to_status:
            return True, f"Tiket sudah dalam status {to_status}.", dict(ticket)

        allowed = ALLOWED_TRANSITIONS.get(current_status, [])
        if to_status not in allowed:
            return False, f"Transisi dari {current_status} ke {to_status} tidak diizinkan.", dict(ticket)

        now = datetime.now(timezone.utc)
        now_str = now.isoformat()
        started_at = ticket['started_at']
        closed_at = ticket['closed_at']
        sla_result = ticket['sla_result']

        if to_status == 'ON_PROGRESS' and not started_at:
            started_at = now_str

        if to_status in ('CLOSED', 'CANCELLED'):
            closed_at = now_str
            if to_status == 'CLOSED':
                # Parse SLA deadline
                deadline = datetime.fromisoformat(ticket['sla_deadline'])
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=timezone.utc)
                if now <= deadline:
                    sla_result = 'IN_SLA'
                else:
                    sla_result = 'OUT_SLA'
        elif to_status == 'OPEN':
            closed_at = None
            sla_result = None

        await conn.execute(
            """
            UPDATE tickets
            SET status = ?,
                started_at = ?,
                closed_at = ?,
                sla_result = ?,
                closing_note = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE ticket_id = ?
            """,
            (to_status, started_at, closed_at, sla_result, note, ticket_id)
        )

        await conn.execute(
            """
            INSERT INTO ticket_events (ticket_id, user_id, from_status, to_status, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ticket_id, user_id, current_status, to_status, note)
        )

        await conn.commit()

    updated = await get_ticket_by_id(ticket_id)
    return True, f"Status tiket {updated['ticket_no']} berhasil diubah ke {to_status}.", updated

async def get_ticket_events(ticket_id: int) -> List[dict]:
    async with get_db() as conn:
        cur = await conn.execute(
            """
            SELECT te.*, u.full_name, u.username, u.role
            FROM ticket_events te
            LEFT JOIN users u ON te.user_id = u.user_id
            WHERE te.ticket_id = ?
            ORDER BY te.created_at ASC
            """,
            (ticket_id,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

# --- ANTRIAN & PENCARIAN ---

async def get_open_tickets() -> List[dict]:
    """
    Get active tickets ordered by SLA deadline ascending (smallest remaining SLA first).
    Status NOT IN ('CLOSED', 'CANCELLED').
    """
    async with get_db() as conn:
        cur = await conn.execute(
            """
            SELECT t.*, c.name as customer_name, c.partner_name, c.address, c.phone,
                   n.region, n.olt, n.pon
            FROM tickets t
            JOIN customers c ON t.customer_id = c.customer_id
            JOIN network_nodes n ON t.node_id = n.node_id
            WHERE t.status NOT IN ('CLOSED', 'CANCELLED')
            ORDER BY datetime(t.sla_deadline) ASC
            """
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def search_tickets(keyword: str) -> List[dict]:
    kw = f"%{keyword.strip()}%"
    async with get_db() as conn:
        cur = await conn.execute(
            """
            SELECT t.*, c.name as customer_name, c.partner_name, n.olt, n.pon
            FROM tickets t
            JOIN customers c ON t.customer_id = c.customer_id
            JOIN network_nodes n ON t.node_id = n.node_id
            WHERE t.ticket_no LIKE ? OR t.crt_number LIKE ? OR c.name LIKE ?
            ORDER BY datetime(t.fu_at) DESC
            LIMIT 15
            """,
            (kw, kw, kw)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

# --- REKAP LAPORAN ---

async def get_tickets_for_report(target_date_str: str) -> List[dict]:
    """
    Target date string in YYYY-MM-DD.
    Section 8 rules:
    Tiket yang:
    (a) masuk pada tanggal rekap (date(fu_at) = target_date),
    (b) masih aktif dari hari sebelumnya (status NOT IN ('CLOSED', 'CANCELLED') AND date(fu_at) < target_date),
    (c) ditutup atau dibatalkan pada tanggal rekap (date(closed_at) = target_date).
    Urut berdasarkan waktu FU naik.
    """
    async with get_db() as conn:
        cur = await conn.execute(
            """
            SELECT t.*, c.name as customer_name, c.partner_name, n.olt, n.pon
            FROM tickets t
            JOIN customers c ON t.customer_id = c.customer_id
            JOIN network_nodes n ON t.node_id = n.node_id
            WHERE (date(t.fu_at) = ?)
               OR (t.status NOT IN ('CLOSED', 'CANCELLED') AND date(t.fu_at) < ?)
               OR (t.status IN ('CLOSED', 'CANCELLED') AND date(t.closed_at) = ?)
            ORDER BY datetime(t.fu_at) ASC
            """,
            (target_date_str, target_date_str, target_date_str)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

# --- SLA REMINDERS ---

async def get_pending_reminders(reminder_type: str, minutes_before: int) -> List[dict]:
    """
    Finds active tickets whose sla_deadline is within minutes_before from now,
    and has not been reminded with reminder_type yet.
    """
    now = datetime.now(timezone.utc)
    async with get_db() as conn:
        cur = await conn.execute(
            """
            SELECT t.*, c.name as customer_name
            FROM tickets t
            JOIN customers c ON t.customer_id = c.customer_id
            LEFT JOIN reminders r ON (r.ticket_id = t.ticket_id AND r.type = ?)
            WHERE t.status NOT IN ('CLOSED', 'CANCELLED')
              AND r.reminder_id IS NULL
              AND datetime(t.sla_deadline) > datetime(?)
              AND (julianday(t.sla_deadline) - julianday(?)) * 1440 <= ?
            """,
            (reminder_type, now.isoformat(), now.isoformat(), minutes_before)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def record_reminder_sent(ticket_id: int, reminder_type: str):
    async with get_db() as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO reminders (ticket_id, type) VALUES (?, ?)",
            (ticket_id, reminder_type)
        )
        await conn.commit()
