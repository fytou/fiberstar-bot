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

def get_main_inline_keyboard(role: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="📋 Antrian Tiket (/open)", callback_data="menu:open"),
            InlineKeyboardButton(text="📊 Rekap WhatsApp (/rekap)", callback_data="menu:rekap")
        ],
        [
            InlineKeyboardButton(text="🔍 Cari Tiket", callback_data="menu:cari"),
            InlineKeyboardButton(text="❓ Panduan Format Tiket", callback_data="menu:help")
        ]
    ]

    if role in ('ADMIN', 'SUPERVISOR'):
        buttons.append([
            InlineKeyboardButton(text="👥 Kelola Whitelist", callback_data="menu:whitelist"),
            InlineKeyboardButton(text="👤 Profil Saya", callback_data="menu:me")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="👤 Profil Saya", callback_data="menu:me")
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_main_reply_keyboard(role: str) -> ReplyKeyboardMarkup:
    keyboard = [
        [
            KeyboardButton(text="📋 Antrian Tiket"),
            KeyboardButton(text="📊 Rekap WhatsApp")
        ],
        [
            KeyboardButton(text="🔍 Cari Tiket"),
            KeyboardButton(text="❓ Panduan")
        ]
    ]

    if role in ('ADMIN', 'SUPERVISOR'):
        keyboard.append([
            KeyboardButton(text="👥 Whitelist"),
            KeyboardButton(text="👤 Profil")
        ])
    else:
        keyboard.append([
            KeyboardButton(text="👤 Profil")
        ])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

@router.message(CommandStart())
async def cmd_start(message: types.Message, current_user: dict):
    role = current_user.get('role', 'TEKNISI')
    name = current_user.get('full_name') or message.from_user.full_name
    
    text = (
        f"👋 *Halo, {name}!*\n"
        f"Selamat datang di *Bot Manajemen Tiket Fiberstar Pekanbaru*.\n"
        f"👤 *Role Anda:* `{role}`\n\n"
        f"Silakan klik tombol menu di bawah untuk mulai mengelola tiket tanpa perlu mengetik perintah manual:"
    )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=get_main_inline_keyboard(role)
    )
    # Also attach reply keyboard
    await message.answer(
        "💡 _Keyboard menu cepat juga sudah aktif di bawah layar Anda._",
        parse_mode="Markdown",
        reply_markup=get_main_reply_keyboard(role)
    )

@router.message(Command("help"))
@router.message(F.text == "❓ Panduan")
async def cmd_help(message: types.Message):
    help_text = (
        f"📖 *PANDUAN BOT TIKET FIBERSTAR PEKANBARU*\n\n"
        f"1️⃣ *Input Tiket FS:*\n"
        f"Cukup paste teks format `[TSHOOT]` dari Fiberstar ke chat bot ini. Bot akan membaca otomatis dan memunculkan tombol konfirmasi simpan.\n\n"
        f"2️⃣ *Alur Status:*\n"
        f"• `OPEN` ➡️ Tiket baru masuk\n"
        f"• `ON_PROGRESS` ➡️ Teknisi sedang menangani\n"
        f"• `PENDING` ➡️ Tertunda (mis. pelanggan belum siap) ⚠️\n"
        f"• `MS_LOST` ➡️ Pelanggan tidak bisa dihubungi ⚠️\n"
        f"• `RESCHEDULED` ➡️ Dijadwalkan ulang\n"
        f"• `CANCELLED` ➡️ Dibatalkan ✅\n"
        f"• `CLOSED` ➡️ Selesai ✅\n\n"
        f"3️⃣ *Perhitungan SLA:*\n"
        f"SLA dihitung *1x24 jam* dari waktu FU to FOP. Bot otomatis mendeteksi apakah penyelesaian berstatus *IN_SLA* atau *OUT_SLA*.\n\n"
        f"4️⃣ *Rekap WhatsApp:*\n"
        f"Klik tombol *Rekap WhatsApp* untuk membuat laporan rekap harian siap salin."
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
async def handle_menu_open(callback: types.CallbackQuery):
    from handlers.tickets import cmd_open
    await callback.answer()
    await cmd_open(callback.message)

@router.callback_query(F.data == "menu:rekap")
async def handle_menu_rekap(callback: types.CallbackQuery):
    from handlers.report import cmd_rekap
    await callback.answer()
    await cmd_rekap(callback.message)

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
async def handle_menu_help(callback: types.CallbackQuery):
    await callback.answer()
    await cmd_help(callback.message)

@router.callback_query(F.data == "menu:me")
async def handle_menu_me(callback: types.CallbackQuery, current_user: dict):
    await callback.answer()
    await cmd_me(callback.message, current_user)

@router.callback_query(F.data == "menu:whitelist")
async def handle_menu_whitelist(callback: types.CallbackQuery, current_user: dict):
    from handlers.admin import cmd_whitelist
    await callback.answer()
    await cmd_whitelist(callback.message, current_user)
