from aiogram import Router, types, F
from aiogram.filters import Command
from database.queries import (
    list_users,
    upsert_user,
    set_user_active,
    set_user_role,
    set_user_vendor,
    set_report_chat_id,
    get_user
)

router = Router()

def is_superadmin(user: dict) -> bool:
    return user.get('role') == 'SUPERADMIN'

def can_view_whitelist(user: dict) -> bool:
    return user.get('role') in ('SUPERADMIN', 'SUPERVISOR')

@router.message(Command("whitelist"))
@router.message(F.text == "👥 Whitelist")
async def cmd_whitelist(message: types.Message, current_user: dict):
    if not can_view_whitelist(current_user):
        await message.answer("⚠️ Anda tidak memiliki izin untuk melihat daftar whitelist.")
        return

    users = await list_users()
    if not users:
        await message.answer("Belum ada user yang terdaftar.")
        return

    lines = ["👥 *DAFTAR PENGGUNA BOT FIBERSTAR:*\n"]
    for u in users:
        status_ico = "🟢" if u['is_active'] else "🔴"
        uname = f"(@{u['username']})" if u.get('username') else ""
        role_ico = {
            'SUPERADMIN': '👑',
            'SUPERVISOR': '🕵️',
            'ADMIN': '📝',
            'TEKNISI': '👷'
        }.get(u['role'], '👤')

        vendor_tag = f"[{u.get('vendor', 'ALL')}]"
        lines.append(
            f"{status_ico} {role_ico} `{u['user_id']}` | *{u['full_name']}* {uname}\n"
            f"   Role: *{u['role']}* | Vendor: *{vendor_tag}* | Status: {'Aktif' if u['is_active'] else 'Nonaktif'}\n"
        )

    if is_superadmin(current_user):
        lines.append(
            "\n💡 *Petunjuk Superadmin:*\n"
            "• Tambah Teknisi: `/adduser <id> TEKNISI <DELTA/INEO> <Nama>`\n"
            "• Tambah Admin: `/adduser <id> ADMIN ALL <Nama>`\n"
            "• Tambah Supervisor: `/adduser <id> SUPERVISOR ALL <Nama>`\n"
            "• Ubah Vendor: `/setvendor <id> <DELTA/INEO>`\n"
            "• Ubah Status: `/toggleuser <id>`"
        )

    await message.answer("\n".join(lines), parse_mode="Markdown")

@router.message(Command("adduser"))
async def cmd_adduser(message: types.Message, current_user: dict):
    if not is_superadmin(current_user):
        await message.answer("⚠️ Perintah penambahan user hanya dapat dilakukan oleh Superadmin.")
        return

    # Syntax: /adduser <telegram_id> <role> [vendor] <nama...>
    args = message.text.split(maxsplit=4)
    if len(args) < 4:
        await message.answer(
            "ℹ️ *Format Tambah Pengguna:*\n"
            "`/adduser <telegram_id> <role> <vendor> <nama>`\n\n"
            "• *Role:* `SUPERADMIN`, `ADMIN`, `SUPERVISOR`, `TEKNISI`\n"
            "• *Vendor:* `DELTA`, `INEO`, atau `ALL`\n\n"
            "Contoh:\n"
            "`/adduser 123456789 TEKNISI DELTA Budi Santoso`\n"
            "`/adduser 987654321 TEKNISI INEO Ahmad`\n"
            "`/adduser 112233445 ADMIN ALL Admin Medan`",
            parse_mode="Markdown"
        )
        return

    raw_id = args[1].strip()
    role = args[2].strip().upper()

    if not raw_id.isdigit():
        await message.answer("❌ Telegram ID harus berupa angka.")
        return

    valid_roles = ('SUPERADMIN', 'ADMIN', 'SUPERVISOR', 'TEKNISI')
    if role not in valid_roles:
        await message.answer(f"❌ Role tidak valid! Pilih salah satu: `{', '.join(valid_roles)}`", parse_mode="Markdown")
        return

    # Check vendor and name
    if len(args) == 4:
        # Vendor not provided, guess default
        vendor = 'ALL' if role in ('SUPERADMIN', 'ADMIN', 'SUPERVISOR') else 'DELTA'
        name = args[3].strip()
    else:
        maybe_vendor = args[3].strip().upper()
        if maybe_vendor in ('DELTA', 'INEO', 'ALL'):
            vendor = maybe_vendor
            name = args[4].strip()
        else:
            vendor = 'ALL' if role in ('SUPERADMIN', 'ADMIN', 'SUPERVISOR') else 'DELTA'
            name = f"{args[3]} {args[4]}".strip()

    user_id = int(raw_id)
    user = await upsert_user(
        user_id=user_id,
        username="",
        full_name=name,
        role=role,
        vendor=vendor,
        is_active=1
    )

    await message.answer(
        f"✅ *Pengguna Berhasil Didaftarkan!*\n\n"
        f"• *ID:* `{user['user_id']}`\n"
        f"• *Nama:* {user['full_name']}\n"
        f"• *Role:* `{user['role']}`\n"
        f"• *Vendor:* `{user.get('vendor', 'ALL')}`\n"
        f"• *Status:* Aktif (Whitelist)",
        parse_mode="Markdown"
    )

@router.message(Command("setvendor"))
async def cmd_setvendor(message: types.Message, current_user: dict):
    if not is_superadmin(current_user):
        await message.answer("⚠️ Hanya Superadmin yang dapat mengubah vendor pengguna.")
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3 or not args[1].strip().isdigit():
        await message.answer("ℹ️ *Format:* `/setvendor <telegram_id> <DELTA / INEO / ALL>`", parse_mode="Markdown")
        return

    user_id = int(args[1].strip())
    vendor = args[2].strip().upper()
    if vendor not in ('DELTA', 'INEO', 'ALL'):
        await message.answer("❌ Vendor harus berupa: `DELTA`, `INEO`, atau `ALL`.", parse_mode="Markdown")
        return

    u = await get_user(user_id)
    if not u:
        await message.answer("❌ Pengguna tidak ditemukan di database.")
        return

    await set_user_vendor(user_id, vendor)
    await message.answer(f"✅ Vendor pengguna `{user_id}` ({u['full_name']}) diubah menjadi *{vendor}*.", parse_mode="Markdown")

@router.message(Command("toggleuser"))
async def cmd_toggleuser(message: types.Message, current_user: dict):
    if not is_superadmin(current_user):
        await message.answer("⚠️ Hanya Superadmin yang dapat mengubah status aktif pengguna.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.answer("ℹ️ *Format:* `/toggleuser <telegram_id>`", parse_mode="Markdown")
        return

    user_id = int(args[1].strip())
    u = await get_user(user_id)
    if not u:
        await message.answer("❌ Pengguna tidak ditemukan di database.")
        return

    new_status = not bool(u['is_active'])
    await set_user_active(user_id, new_status)
    status_str = "Diaktifkan (Whitelist)" if new_status else "Dinonaktifkan (Blokir)"

    await message.answer(
        f"✅ Status pengguna `{user_id}` ({u['full_name']}) telah diubah menjadi: *{status_str}*",
        parse_mode="Markdown"
    )

@router.message(Command("setchat"))
async def cmd_setchat(message: types.Message, current_user: dict):
    if not is_superadmin(current_user):
        await message.answer("⚠️ Hanya Superadmin yang dapat mengatur grup notifikasi.")
        return

    chat_id = message.chat.id
    await set_report_chat_id(chat_id)
    await message.answer(f"✅ Chat ID grup ini (`{chat_id}`) telah disimpan sebagai grup notifikasi tim Pekanbaru.")
