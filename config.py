import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
]
DEFAULT_TEAM_NAME = os.getenv("DEFAULT_TEAM_NAME", "Pekanbaru")
TIMEZONE_NAME = os.getenv("TIMEZONE", "Asia/Jakarta")
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "fiberstar.db"))
SLA_HOURS = int(os.getenv("SLA_HOURS", "24"))
