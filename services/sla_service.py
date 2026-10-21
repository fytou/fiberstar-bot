from datetime import datetime, timezone, timedelta
import zoneinfo
from typing import Tuple, Optional
from config import TIMEZONE_NAME

tz = zoneinfo.ZoneInfo(TIMEZONE_NAME)

def parse_iso_dt(dt_str: str) -> datetime:
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz)

def format_duration(seconds: float) -> str:
    total_minutes = int(abs(seconds) // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours > 0:
        return f"{hours}j {minutes}m"
    return f"{minutes}m"

def get_sla_status(deadline_str: str) -> Tuple[str, str, str]:
    """
    Returns (badge, remaining_label, urgency_level)
    urgency_level: 'OVERDUE' | 'CRITICAL' | 'SAFE'
    """
    now = datetime.now(tz)
    deadline = parse_iso_dt(deadline_str)
    delta = (deadline - now).total_seconds()

    if delta < 0:
        dur = format_duration(delta)
        return "🔴 LEWAT SLA", f"Lewat {dur}", "OVERDUE"
    elif delta <= 3600:
        dur = format_duration(delta)
        return "🟡 < 1 JAM", f"Sisa {dur}", "CRITICAL"
    else:
        dur = format_duration(delta)
        return "🟢 AMAN", f"Sisa {dur}", "SAFE"

def evaluate_closing_sla(fu_at_str: str, deadline_str: str, closed_at_str: Optional[str] = None) -> Tuple[str, str]:
    """
    Evaluates whether ticket was closed within SLA.
    Returns (result, note_addon) where result is 'IN_SLA' or 'OUT_SLA'.
    """
    deadline = parse_iso_dt(deadline_str)
    if closed_at_str:
        closed_at = parse_iso_dt(closed_at_str)
    else:
        closed_at = datetime.now(tz)

    closed_time_hm = closed_at.strftime("%H:%M")

    if closed_at <= deadline:
        return "IN_SLA", f"CLOSE IN SLA {closed_time_hm}"
    else:
        diff_seconds = (closed_at - deadline).total_seconds()
        dur = format_duration(diff_seconds)
        return "OUT_SLA", f"CLOSE OUT SLA {closed_time_hm}, lewat {dur}"
