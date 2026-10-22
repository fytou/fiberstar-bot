from aiogram import Router, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from database.queries import get_user, list_users

router = Router()

def get_main_inline_keyboard(role: str, vendor: str = 'ALL') -> InlineKeyboardMarkup:
    buttons = []

    if role == 'SUPERADMIN':
        buttons = [
            [
                InlineKeyboardButton(text="📋 Antrian Tiket (/open)", callback_data="menu:open"),
                InlineKeyboardButton(text="📊 Rekap WhatsApp (/rekap)", callback_data="menu:rekap")
            ],
            [
                InlineKeyboardButton(text="🔍 Cari Tiket", callback_data="menu:cari"),
                InlineKeyboardButton(text="👥 Kelola Whitelist", callback_data="menu:whitelist")
            ],
            [
                InlineKeyboardButton(text="❓ Panduan Format", callback_data="menu:help"),
                InlineKeyboardButton(text="👤 Profil Saya", callback_data="menu:me")
            ]
        ]
    elif role == 'SUPERVISOR':
        buttons = [
            [
                InlineKeyboardButton(text="📋 Pantau Antrian Tiket", callback_data="menu:open"),
                InlineKeyboardButton(text="📊 Rekap WhatsApp", callback_data="menu:rekap")
            ],
            [
                InlineKeyboardButton(text="🔍 Cari Tiket", callback_data="menu:cari"),
                InlineKeyboardButton(text="👥 Daftar Tim", callback_data="menu:whitelist")
            ],
            [
                InlineKeyboardButton(text="❓ Panduan", callback_data="menu:help"),
                InlineKeyboardButton(text="👤 Profil Saya", callback_data="menu:me")
            ]
        ]
    elif role == 'ADMIN':
        # Admin tugasnya khusus input tiket
        buttons = [
            [
                InlineKeyboardButton(text="📥 Panduan Input Tiket FS", callback_data="menu:help"),
                InlineKeyboardButton(text="👤 Profil Saya", callback_data="menu:me")
            ]
        ]
    else:  # TEKNISI
        vendor_tag = f"Vendor {vendor}" if vendor in ('DELTA', 'INEO') else "Teknisi"
        buttons = [
            [
                InlineKeyboardButton(text=f"📋 Antrian Tiket ({vendor_tag})", callback_data="menu:open"),
                InlineKeyboardButton(text="🔍 Cari Tiket", callback_data="menu:cari")
            ],
            [
                InlineKeyboardButton(text="❓ Panduan Status", callback_data="menu:help"),
                InlineKeyboardButton(text="👤 Profil Saya", callback_data="menu:me")
            ]
        ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_main_reply_keyboard(role: str, vendor: str = 'ALL') -> ReplyKeyboardMarkup:
    keyboard = []

    if role == 'SUPERADMIN':
        keyboard = [
            [KeyboardButton(text="📋 Antrian Tiket"), KeyboardButton(text="📊 Rekap WhatsApp")],
            [KeyboardButton(text="🔍 Cari Tiket"), KeyboardButton(text="👥 Whitelist")],
            [KeyboardButton(text="❓ Panduan"), KeyboardButton(text="👤 Profil")]
        ]
    elif role == 'SUPERVISOR':
        keyboard = [
            [KeyboardButton(text="📋 Antrian Tiket"), KeyboardButton(text="📊 Rekap WhatsApp")],
            [KeyboardButton(text="🔍 Cari Tiket"), KeyboardButton(text="👥 Whitelist")],
            [KeyboardButton(text="❓ Panduan"), KeyboardButton(text="👤 Profil")]
        ]
    elif role == 'ADMIN':
        keyboard = [
            [KeyboardButton(text="📥 Petunjuk Input Tiket")],
            [KeyboardButton(text="❓ Panduan"), KeyboardButton(text="👤 Profil")]
        ]
    else: # TEKNISI
        keyboard = [
            [KeyboardButton(text="📋 Antrian Tiket"), KeyboardButton(text="🔍 Cari Tiket")],
            [KeyboardButton(text="❓ Panduan"), KeyboardButton(text="👤 Profil")]
        ]

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

@router.message(CommandStart())
async def cmd_start(message: types.Message, current_user: dict):
    role = current_user.get('role', 'TEKNISI')
    vendor = current_user.get('vendor', 'ALL')
    name = current_user.get('full_name') or message.from_user.full_name

    role_desc = {
        'SUPERADMIN': '👑 Superadmin (Akses Penuh)',
        'SUPERVISOR': '🕵️ Supervisor (Pengawas & Pemantau Tiket)',
        'ADMIN': '📝 Admin (Petugas Input Tiket FS)',
        'TEKNISI': f'👷 Teknisi Vendor {vendor}'
    }.get(role, role)

    text = (
        f"👋 *Halo, {name}!* \n"
        f"Selamat datang di *Bot Tiket Fiberstar Pekanbaru*.\n"
        f"🔰 *Role Anda:* `{role_desc}`\n"
    )

    if role == 'ADMIN':
        text += (
            f"\n📌 *Tugas Admin:* Menginput data tiket masuk dari Fiberstar.\n"
            f"Silakan langsung paste teks tiket format `[TSHOOT]` ke chat ini untuk disimpan."
        )
    elif role == 'SUPERVISOR':
        text += (
            f"\n📌 *Tugas Supervisor:* Mengawasi tiket masuk, memeriksa garansi DELTA / INEO, "
            f"memantau tiket yang sedang dikerjakan teknisi, SLA, dan rekap harian."
        )
    elif role == 'TEKNISI':
        if vendor == 'DELTA':
            text += (
                f"\n📌 *Teknisi DELTA:* Anda menangani tiket garansi DELTA.\n"
                f"⚡ *Catatan Khusus:* Jika menemukan kendala *ODP Lost*, gunakan tombol *Oper ke INEO* pada tiket agar otomatis dilimpahkan ke tim INEO."
            )
        elif vendor == 'INEO':
            text += (
                f"\n📌 *Teknisi INEO:* Anda menangani tiket garansi INEO dan semua tiket operan *ODP Lost* dari DELTA."
            )
    else:
        text += f"\nSilakan pilih menu di bawah ini:"

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=get_main_inline_keyboard(role, vendor)
    )
    await message.answer(
        "💡 _Menu cepat juga aktif di papan ketik bawah layar Anda._",
        parse_mode="Markdown",
        reply_markup=get_main_reply_keyboard(role, vendor)
    )

@router.message(Command("help"))
@router.message(F.text == "❓ Panduan")
@router.message(F.text == "📥 Petunjuk Input Tiket")
async def cmd_help(message: types.Message, current_user: dict):
    role = current_user.get('role', 'TEKNISI')
    help_text = (
        f"📖 *PANDUAN ALUR BOT TIKET FIBERSTAR PEKANBARU*\n\n"
        f"1️⃣ *Peran Pengguna:*\n"
        f"• *Superadmin*: Memiliki akses penuh (whitelist, rekap, antrian, oper tiket).\n"
        f"• *Admin*: Khusus input tiket `[TSHOOT]` dari Medan ke sistem.\n"
        f"• *Supervisor*: Memantau tiket masuk, garansi vendor, progress, dan SLA.\n"
        f"• *Teknisi*: Memproses tiket sesuai vendor masing-masing (*DELTA* atau *INEO*).\n\n"
        f"2️⃣ *Alur Khusus ODP Lost (DELTA ➡️ INEO):*\n"
        f"Jika teknisi DELTA mendapati kendala *ODP Lost*, tekan tombol `🔄 Oper ke INEO (ODP Lost)`. "
        f"Tiket akan otomatis dialihkan ke antrian teknisi INEO karena ODP Lost hanya ditangani oleh INEO.\n\n"
        f"3️⃣ *Format Input Tiket:*\n"
        f"Kirimkan teks format `[TSHOOT]` Fiberstar. Bot akan mengenali otomatis nomor tiket, CRT, pelanggan, OLT/PON, dan Garansi (DELTA / INEO)."
    )
    await message.answer(help_text, parse_mode="Markdown")

@router.message(Command("me"))
@router.message(F.text == "👤 Profil")
async def cmd_me(message: types.Message, current_user: dict):
    u = current_user
    text = (
        f"👤 *Profil Pengguna:*\n"
        f"• *ID Telegram:* `{u['user_id']}`\n"
        f"• *Nama:* {u['full_name']}\n"
        f"• *Username:* @{u['username'] if u.get('username') else '-'}\n"
        f"• *Role:* `{u['role']}`\n"
        f"• *Vendor:* `{u.get('vendor', 'ALL')}`\n"
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

# --- INLINE MENU CALLBACK HANDLERS ---

@router.callback_query(F.data == "menu:open")
async def handle_menu_open(callback: types.CallbackQuery, current_user: dict):
    from handlers.tickets import show_open_tickets
    await callback.answer()
    await show_open_tickets(callback.message, current_user)

@router.callback_query(F.data == "menu:rekap")
async def handle_menu_rekap(callback: types.CallbackQuery, current_user: dict):
    from handlers.report import cmd_rekap
    await callback.answer()
    await cmd_rekap(callback.message, current_user)

@router.callback_query(F.data == "menu:cari")
async def handle_menu_cari(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "🔍 *Pencarian Tiket*\n"
        "Ketik perintah pencarian dengan format:\n"
        "`/cari <nomor_tiket / crt / nama_pelanggan>`\n\n"
        "Contoh: `/cari CRT1000` atau `/cari Budi`",
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "menu:help")
async def handle_menu_help(callback: types.CallbackQuery, current_user: dict):
    await callback.answer()
    await cmd_help(callback.message, current_user)

@router.callback_query(F.data == "menu:me")
async def handle_menu_me(callback: types.CallbackQuery, current_user: dict):
    await callback.answer()
    await cmd_me(callback.message, current_user)

@router.callback_query(F.data == "menu:whitelist")
async def handle_menu_whitelist(callback: types.CallbackQuery, current_user: dict):
    from handlers.admin import cmd_whitelist
    await callback.answer()
    await cmd_whitelist(callback.message, current_user)
