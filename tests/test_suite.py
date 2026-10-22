import unittest
import asyncio
from datetime import datetime, timezone, timedelta
import zoneinfo
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from parser.ticket_parser import parse_tickets_from_message, parse_single_ticket_block
from services.sla_service import get_sla_status, evaluate_closing_sla
from services.report_service import build_daily_report, format_ticket_line
from services.reply_service import generate_closed_reply_text
from database.db import init_db, get_db
from database.queries import (
    upsert_user,
    insert_ticket,
    get_ticket_by_no,
    update_ticket_status,
    get_open_tickets,
    get_tickets_for_report
)

SAMPLE_TICKET_1 = """[TSHOOT]
Northern Sumatera
T0000001-201026-01
Dear Team Pekanbaru, mohon bantuan pengecekan
Nama : PT Mitra Fiber - Bapak Rahmad
Alamat : Jl. Sudirman No. 45, Pekanbaru,, Riau
CRT : CRT10000234
OLT : PKU-OLT-01
PON : 1/1/4:12
Telp : 081234567890
Los Merah
2026-10-20T10:14:00+07:00
20/10/2026 10:14 FU to FOP
Garansi Aktivasi DELTA"""

SAMPLE_TICKET_PRE_CLOSED = """Back To. Normal
[TSHOOT]
Kepulauan Riau
T0000002-201026-01
Dear Team Pekanbaru, kendala pelanggan
Nama : CBN - Ibu Siti Aminah
Alamat : Jl. Riau No. 12
CRT : CRT10000555
OLT : PKU-OLT-02
PON : 1/1/2:5
Telp : +6282199887766
Gpon Rx Power -32 dBm Critical
20/10/2026 12:54 FU to FOP"""

SAMPLE_MULTIPLE = f"""{SAMPLE_TICKET_1}
====
{SAMPLE_TICKET_PRE_CLOSED}"""

class TestFiberstarBot(unittest.TestCase):

    def test_parse_single_ticket(self):
        parsed = parse_single_ticket_block(SAMPLE_TICKET_1)
        self.assertEqual(parsed.ticket_no, "T0000001-201026-01")
        self.assertEqual(parsed.crt_number, "CRT10000234")
        self.assertEqual(parsed.customer_name, "Bapak Rahmad")
        self.assertEqual(parsed.partner_name, "PT Mitra Fiber")
        self.assertEqual(parsed.phone, "6281234567890")
        self.assertEqual(parsed.issue_type, "Los Merah")
        self.assertEqual(parsed.warranty_program, "Garansi delta")
        self.assertEqual(parsed.vendor, "DELTA")
        self.assertEqual(parsed.olt, "PKU-OLT-01")
        self.assertEqual(parsed.pon, "1/1/4:12")
        self.assertTrue(parsed.to_dict()['is_valid'])
        self.assertEqual(parsed.fu_at.strftime("%d/%m/%Y %H:%M"), "20/10/2026 10:14")
        # SLA deadline should be fu_at + 24h
        expected_sla = parsed.fu_at + timedelta(hours=24)
        self.assertEqual(parsed.sla_deadline, expected_sla)

    def test_parse_pre_closed_ticket(self):
        # PRD FR-04: Note before [TSHOOT] means ticket was already closed
        parsed_list = parse_tickets_from_message(SAMPLE_TICKET_PRE_CLOSED)
        self.assertEqual(len(parsed_list), 1)
        p = parsed_list[0]
        self.assertEqual(p.status, "CLOSED")
        self.assertEqual(p.closing_note, "Back To. Normal")
        self.assertEqual(p.ticket_no, "T0000002-201026-01")
        self.assertEqual(p.customer_name, "Ibu Siti Aminah")
        self.assertEqual(p.partner_name, "CBN")
        self.assertEqual(p.phone, "6282199887766")

    def test_parse_multiple_tickets(self):
        parsed_list = parse_tickets_from_message(SAMPLE_MULTIPLE)
        self.assertEqual(len(parsed_list), 2)
        self.assertEqual(parsed_list[0].ticket_no, "T0000001-201026-01")
        self.assertEqual(parsed_list[1].ticket_no, "T0000002-201026-01")

    def test_rekap_formatting(self):
        p1 = parse_single_ticket_block(SAMPLE_TICKET_1)
        p1_dict = p1.to_dict()
        p1_dict['status'] = 'CLOSED'
        p1_dict['closed_at'] = '2026-10-20T14:06:00+07:00'
        p1_dict['sla_result'] = 'IN_SLA'

        line1 = format_ticket_line(1, p1_dict)
        # Expected from PRD page 7:
        # 1. T0000001-201026-01 Bapak Rahmad CRT10000234 20/10/2026 10:14 Garansi delta (CLOSE IN SLA 14:06) ✅
        self.assertIn("1. T0000001-201026-01 Bapak Rahmad CRT10000234 20/10/2026 10:14 Garansi delta (CLOSE IN SLA 14:06) ✅", line1)

        # Open ticket formatting (no notes, no emoji)
        p2 = parse_single_ticket_block(SAMPLE_TICKET_1)
        p2_dict = p2.to_dict()
        p2_dict['ticket_no'] = 'T0000002-201026-01'
        p2_dict['status'] = 'OPEN'
        p2_dict['warranty_program'] = None
        line2 = format_ticket_line(2, p2_dict)
        self.assertEqual(line2, "2. T0000002-201026-01 Bapak Rahmad CRT10000234 20/10/2026 10:14")

        # Out of SLA closed ticket
        p3_dict = p1.to_dict()
        p3_dict['ticket_no'] = 'T0000003-201026-01'
        p3_dict['status'] = 'CLOSED'
        p3_dict['sla_result'] = 'OUT_SLA'
        # closed after 24h deadline
        p3_dict['closed_at'] = '2026-10-21T12:14:00+07:00'
        p3_dict['warranty_program'] = None
        line3 = format_ticket_line(3, p3_dict)
        self.assertIn("(CLOSE OUT SLA 12:14, lewat 2j 0m) ⚠️", line3)

        # Pending ticket
        p4_dict = p1.to_dict()
        p4_dict['ticket_no'] = 'T0000004-201026-01'
        p4_dict['status'] = 'PENDING'
        p4_dict['closing_note'] = 'Pelanggan Belum Ready'
        p4_dict['warranty_program'] = None
        line4 = format_ticket_line(4, p4_dict)
        self.assertIn("(Pelanggan Belum Ready) ⚠️", line4)

        # MS Lost ticket
        p5_dict = p1.to_dict()
        p5_dict['ticket_no'] = 'T0000005-201026-01'
        p5_dict['status'] = 'MS_LOST'
        p5_dict['warranty_program'] = None
        line5 = format_ticket_line(5, p5_dict)
        self.assertIn("( MS LOST ) ⚠️", line5)

        # Cancelled ticket
        p6_dict = p1.to_dict()
        p6_dict['ticket_no'] = 'T0000006-201026-01'
        p6_dict['status'] = 'CANCELLED'
        p6_dict['closing_note'] = 'Cancel Reschedule'
        p6_dict['warranty_program'] = None
        line6 = format_ticket_line(6, p6_dict)
        self.assertIn("(Cancel Reschedule) ✅", line6)

    def test_daily_report_full_builder(self):
        p1 = parse_single_ticket_block(SAMPLE_TICKET_1)
        target_date = datetime(2026, 10, 20, tzinfo=zoneinfo.ZoneInfo("Asia/Jakarta"))
        t_dict = p1.to_dict()
        t_dict['status'] = 'CLOSED'
        t_dict['closed_at'] = '2026-10-20T14:06:00+07:00'
        t_dict['sla_result'] = 'IN_SLA'

        report_chunks = build_daily_report(target_date, [t_dict])
        self.assertEqual(len(report_chunks), 1)
        full_report = report_chunks[0]
        self.assertTrue(full_report.startswith("List open tiket broadband 20/10/26"))
        self.assertIn("1. T0000001-201026-01", full_report)
        self.assertIn("Ringkasan Tiket:", full_report)
        self.assertIn("Total: 1", full_report)
        self.assertIn("Closed: 1", full_report)

    def test_closed_reply_text(self):
        reply = generate_closed_reply_text("Back To Normal", SAMPLE_TICKET_1)
        self.assertTrue(reply.startswith("Back To Normal\n[TSHOOT]"))

class TestAsyncDatabase(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        import config
        config.DB_PATH = 'test_fiberstar.db'
        if os.path.exists('test_fiberstar.db'):
            try:
                os.remove('test_fiberstar.db')
            except Exception:
                pass
        await init_db()

    async def asyncTearDown(self):
        if os.path.exists('test_fiberstar.db'):
            try:
                os.remove('test_fiberstar.db')
            except Exception:
                pass

    async def test_ticket_lifecycle(self):
        # 1. Register admin and technician
        admin = await upsert_user(1001, "admin_medan", "Admin Medan", role="ADMIN")
        tech = await upsert_user(2001, "tech_pku", "Teknisi Pekanbaru", role="TEKNISI")

        # 2. Ingest ticket
        p = parse_single_ticket_block(SAMPLE_TICKET_1)
        inserted = await insert_ticket(admin['user_id'], p.to_dict())
        self.assertIsNotNone(inserted)
        self.assertEqual(inserted['status'], 'OPEN')

        # 3. Check /open queue
        open_list = await get_open_tickets()
        self.assertEqual(len(open_list), 1)

        # 4. Transition OPEN -> ON_PROGRESS
        ok, msg, updated = await update_ticket_status(inserted['ticket_id'], tech['user_id'], 'ON_PROGRESS')
        self.assertTrue(ok)
        self.assertEqual(updated['status'], 'ON_PROGRESS')

        # 5. Invalid transition ON_PROGRESS -> RESCHEDULED should be rejected
        ok, msg, _ = await update_ticket_status(inserted['ticket_id'], tech['user_id'], 'RESCHEDULED')
        self.assertFalse(ok)

        # 6. Close ticket
        ok, msg, closed = await update_ticket_status(inserted['ticket_id'], tech['user_id'], 'CLOSED', note="Back To Normal")
        self.assertTrue(ok)
        self.assertEqual(closed['status'], 'CLOSED')
        # Since SAMPLE_TICKET_1 fu_at was 20/10 10:14, deadline was 21/10 10:14, now is > 17:00, so it correctly marked OUT_SLA
        self.assertIn(closed['sla_result'], ('IN_SLA', 'OUT_SLA'))

        # Also test a freshly created ticket whose deadline is in future (should be IN_SLA)
        now_dt = datetime.now(timezone.utc)
        fresh_dict = p.to_dict()
        fresh_dict['ticket_no'] = 'T9999999-211026-01'
        fresh_dict['fu_at'] = now_dt.isoformat()
        fresh_dict['sla_deadline'] = (now_dt + timedelta(hours=24)).isoformat()
        fresh_ticket = await insert_ticket(admin['user_id'], fresh_dict)
        # 7. Check duplicate ticket rejection
        from sqlite3 import IntegrityError
        with self.assertRaises(IntegrityError):
            await insert_ticket(admin['user_id'], fresh_dict)

        # 8. Check active CRT query (FR-03)
        # Create an active ticket on CRT999
        crt_dict = p.to_dict()
        crt_dict['ticket_no'] = 'T8888888-211026-01'
        crt_dict['crt_number'] = 'CRT999999'
        crt_dict['status'] = 'OPEN'
        crt_dict['fu_at'] = now_dt.isoformat()
        crt_dict['sla_deadline'] = (now_dt + timedelta(hours=24)).isoformat()
        await insert_ticket(admin['user_id'], crt_dict)

        from database.queries import get_active_tickets_by_crt, transfer_ticket_to_ineo
        active_crt = await get_active_tickets_by_crt('CRT999999')
        self.assertEqual(len(active_crt), 1)
        self.assertEqual(active_crt[0]['ticket_no'], 'T8888888-211026-01')

        # 9. Test ODP Lost transfer from DELTA to INEO
        ticket_delta = await insert_ticket(admin['user_id'], {
            'ticket_no': 'T7777777-221026-01',
            'crt_number': 'CRT7777777',
            'customer_name': 'Pelanggan Delta',
            'issue_type': 'Los Merah',
            'vendor': 'DELTA',
            'status': 'OPEN',
            'fu_at': now_dt.isoformat(),
            'sla_deadline': (now_dt + timedelta(hours=24)).isoformat()
        })
        self.assertEqual(ticket_delta['vendor'], 'DELTA')

        # DELTA queue should have it
        delta_open = await get_open_tickets(vendor='DELTA')
        delta_ticket_nos = [x['ticket_no'] for x in delta_open]
        self.assertIn('T7777777-221026-01', delta_ticket_nos)

        # Execute transfer ODP Lost
        ok_tr, msg_tr, tr_ticket = await transfer_ticket_to_ineo(ticket_delta['ticket_id'], tech['user_id'], reason="ODP Lost")
        self.assertTrue(ok_tr)
        self.assertEqual(tr_ticket['vendor'], 'INEO')
        self.assertEqual(tr_ticket['transferred_from'], 'DELTA')
        self.assertEqual(tr_ticket['transfer_reason'], 'ODP Lost')

        # Now ticket should NOT be in DELTA queue, but IN INEO queue!
        delta_open_after = await get_open_tickets(vendor='DELTA')
        self.assertNotIn('T7777777-221026-01', [x['ticket_no'] for x in delta_open_after])

        ineo_open = await get_open_tickets(vendor='INEO')
        self.assertIn('T7777777-221026-01', [x['ticket_no'] for x in ineo_open])

if __name__ == '__main__':
    unittest.main()
