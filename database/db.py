import aiosqlite
import logging
from contextlib import asynccontextmanager
import config

logger = logging.getLogger(__name__)

CREATE_TABLES_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS teams (
    team_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    report_chat_id INTEGER
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(team_id),
    username TEXT,
    full_name TEXT,
    role TEXT NOT NULL CHECK(role IN ('SUPERADMIN', 'ADMIN', 'SUPERVISOR', 'TEKNISI')),
    vendor TEXT NOT NULL DEFAULT 'ALL' CHECK(vendor IN ('DELTA', 'INEO', 'ALL')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_name TEXT,
    name TEXT NOT NULL,
    address TEXT,
    phone TEXT
);

CREATE TABLE IF NOT EXISTS network_nodes (
    node_id INTEGER PRIMARY KEY AUTOINCREMENT,
    region TEXT,
    olt TEXT,
    pon TEXT,
    team_id INTEGER NOT NULL REFERENCES teams(team_id)
);

CREATE TABLE IF NOT EXISTS raw_messages (
    raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(user_id),
    message_text TEXT NOT NULL,
    source_format TEXT DEFAULT 'TSHOOT_V1',
    parse_status TEXT NOT NULL CHECK(parse_status IN ('SUCCESS', 'PARTIAL', 'FAILED')),
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_no TEXT NOT NULL UNIQUE,
    crt_number TEXT NOT NULL,
    assigned_user_id INTEGER REFERENCES users(user_id),
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    node_id INTEGER NOT NULL REFERENCES network_nodes(node_id),
    raw_id INTEGER REFERENCES raw_messages(raw_id),
    vendor TEXT NOT NULL DEFAULT 'DELTA' CHECK(vendor IN ('DELTA', 'INEO')),
    transferred_from TEXT,
    transfer_reason TEXT,
    issue_type TEXT NOT NULL,
    issue_detail TEXT,
    rx_power_dbm REAL,
    warranty_program TEXT,
    status TEXT NOT NULL CHECK(status IN ('OPEN', 'ON_PROGRESS', 'PENDING', 'MS_LOST', 'RESCHEDULED', 'CANCELLED', 'CLOSED')),
    reported_at TIMESTAMP,
    fu_at TIMESTAMP NOT NULL,
    sla_deadline TIMESTAMP NOT NULL,
    sla_result TEXT CHECK(sla_result IN ('IN_SLA', 'OUT_SLA')),
    started_at TIMESTAMP,
    closed_at TIMESTAMP,
    closing_note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ticket_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES tickets(ticket_id),
    user_id INTEGER REFERENCES users(user_id),
    from_status TEXT,
    to_status TEXT NOT NULL,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sla_rules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_pattern TEXT NOT NULL,
    sla_minutes INTEGER NOT NULL DEFAULT 1440,
    basis TEXT NOT NULL CHECK(basis IN ('FU_AT', 'REPORTED_AT')),
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS bot_sessions (
    user_id INTEGER PRIMARY KEY,
    state TEXT,
    ticket_id INTEGER,
    payload TEXT,
    expires_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reminders (
    reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES tickets(ticket_id),
    type TEXT NOT NULL CHECK(type IN ('SLA_60', 'SLA_15')),
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticket_id, type)
);

CREATE INDEX IF NOT EXISTS idx_tickets_status_sla ON tickets(status, sla_deadline);
CREATE INDEX IF NOT EXISTS idx_tickets_assigned_fu ON tickets(assigned_user_id, fu_at);
CREATE INDEX IF NOT EXISTS idx_tickets_crt ON tickets(crt_number);
CREATE INDEX IF NOT EXISTS idx_tickets_fu_at ON tickets(fu_at);
CREATE INDEX IF NOT EXISTS idx_tickets_vendor ON tickets(vendor);
"""

@asynccontextmanager
async def get_db():
    conn = await aiosqlite.connect(config.DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        await conn.close()

async def run_migrations(conn: aiosqlite.Connection):
    """Safely adds missing columns to existing SQLite database without losing data."""
    # Check users columns
    cur = await conn.execute("PRAGMA table_info(users)")
    user_cols = [row['name'] for row in await cur.fetchall()]
    if 'vendor' not in user_cols:
        await conn.execute("ALTER TABLE users ADD COLUMN vendor TEXT NOT NULL DEFAULT 'ALL'")
        logger.info("Migrated users: added vendor column.")

    # Check tickets columns
    cur = await conn.execute("PRAGMA table_info(tickets)")
    ticket_cols = [row['name'] for row in await cur.fetchall()]
    if 'vendor' not in ticket_cols:
        await conn.execute("ALTER TABLE tickets ADD COLUMN vendor TEXT NOT NULL DEFAULT 'DELTA'")
        logger.info("Migrated tickets: added vendor column.")
    if 'transferred_from' not in ticket_cols:
        await conn.execute("ALTER TABLE tickets ADD COLUMN transferred_from TEXT")
        logger.info("Migrated tickets: added transferred_from column.")
    if 'transfer_reason' not in ticket_cols:
        await conn.execute("ALTER TABLE tickets ADD COLUMN transfer_reason TEXT")
        logger.info("Migrated tickets: added transfer_reason column.")

async def init_db():
    async with get_db() as conn:
        await conn.executescript(CREATE_TABLES_SQL)
        await run_migrations(conn)

        # Ensure default team exists
        cur = await conn.execute("SELECT team_id FROM teams WHERE name = ?", (config.DEFAULT_TEAM_NAME,))
        team = await cur.fetchone()
        if not team:
            await conn.execute("INSERT INTO teams (name) VALUES (?)", (config.DEFAULT_TEAM_NAME,))
        
        # Ensure default SLA rule exists
        cur = await conn.execute("SELECT rule_id FROM sla_rules WHERE issue_pattern = '%'", ())
        rule = await cur.fetchone()
        if not rule:
            await conn.execute(
                "INSERT INTO sla_rules (issue_pattern, sla_minutes, basis, is_active) VALUES (?, ?, ?, 1)",
                ('%', config.SLA_HOURS * 60, 'FU_AT')
            )
        await conn.commit()
    logger.info("Database initialized successfully.")
