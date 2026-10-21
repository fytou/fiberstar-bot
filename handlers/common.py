from aiogram import Router, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from database.queries import get_user

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message, current_user: dict):
    role = current_user.get('role', 'TEKNISI')
    name = current_user.get('full_name') or message.from_user.full_name
    
    text = (
        f"👋 *Halo, {name}! Selamat datang di Bot Manajemen Tiket Fiberstar Pekanbaru.*\n"
        f"👤 *Role Anda:* `{role}`\n\n"
        f"📋 *Menu Perintah:*\n"
        f"• `/open` — Lihat daftar antrian tiket aktif (diurutkan sisa SLA)\n"
        f"• `/rekap` — Buat format laporan rekap harian untuk WhatsApp\n"
        f"• `/cari <kata_kunci>` — Cari tiket via No Tiket, CRT, atau Nama\n"
        f"• `/help` — Petunjuk lengkap & contoh format tiket\n"
        f"• `/me` — Info profil & status whitelist Anda\n"
    )

    if role in ('ADMIN', 'SUPERVISOR'):
        text += (
            f"\n🛠 *Menu Admin / Supervisor:*\n"
            f"• Kirim / paste teks tiket FS berformat `[TSHOOT]` untuk input tiket\n"
            f"• `/whitelist` — Kelola daftar teknisi & perizinan user\n"
            f"• `/adduser <id> <role> <nama>` — Tambah teknisi ke whitelist\n"
            f"• `/setchat` — Daftarkan grup ini sebagai grup notifikasi tim\n"
        )
    else:
        text += (
            f"\n💡 *Catatan Teknisi:*\n"
            f"Anda dapat mengubah status tiket, melihat detail riwayat, dan mengambil teks balasan WA saat tiket selesai."
        )

    await message.answer(text, parse_mode="Markdown")

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        f"📖 *PANDUAN BOT TIKET FIBERSTAR PEKANBARU*\n\n"
        f"1️⃣ *Input Tiket FS:*\n"
        f"Admin di Medan dapat langsung menempelkan teks format `[TSHOOT]` dari Fiberstar ke bot. Satu pesan bisa memuat satu atau beberapa tiket (dipisah `====` atau `[TSHOOT]`).\n\n"
        f"2️⃣ *Alur Status:*\n"
        f"• `OPEN` ➡️ Tiket baru masuk\n"
        f"• `ON_PROGRESS` ➡️ Teknisi sedang menangani kendala\n"
        f"• `PENDING` ➡️ Tertunda (mis. pelanggan belum siap) ⚠️\n"
        f"• `MS_LOST` ➡️ Pelanggan tidak bisa dihubungi ⚠️\n"
        f"• `RESCHEDULED` ➡️ Dijadwalkan ulang\n"
        f"• `CANCELLED` ➡️ Dibatalkan ✅\n"
        f"• `CLOSED` ➡️ Selesai ✅\n\n"
        f"3️⃣ *Perhitungan SLA:*\n"
        f"SLA dihitung *1x24 jam* berturut-turut dari waktu FU to FOP. Bot akan menghitung apakah tiket diselesaikan *IN_SLA* atau *OUT_SLA* beserta selisih waktunya.\n\n"
        f"4️⃣ *Rekap WhatsApp:*\n"
        f"Ketik `/rekap` untuk menghasilkan laporan harian siap salin ke WhatsApp tim/klien tanpa perlu ketik manual."
    )
    await message.answer(help_text, parse_mode="Markdown")

@router.message(Command("me"))
async def cmd_me(message: types.Message, current_user: dict):
    u = current_user
    text = (
        f"👤 *Profil Pengguna:*\n"
        f"• *ID Telegram:* `{u['user_id']}`\n"
        f"• *Nama:* {u['full_name']}\n"
        f"• *Username:* @{u['username'] if u.get('username') else '-'}\n"
        f"• *Role:* `{u['role']}`\n"
        f"• *Status Whitelist:* {'✅ Aktif' if u['is_active'] else '❌ Dinonaktifkan'}\n"
        f"• *Tim:* Pekanbaru"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Tidak ada proses yang sedang berlangsung.")
        return
    await state.clear()
    await message.answer("🚫 Operasi telah dibatalkan.")
