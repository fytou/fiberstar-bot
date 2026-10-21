from aiogram import Router, types, F
from aiogram.filters import Command
from database.queries import list_users, upsert_user, set_user_active, set_report_chat_id

router = Router()

def is_admin(user: dict) -> bool:
    return user.get('role') == 'ADMIN'

@router.message(Command("whitelist"))
async def cmd_whitelist(message: types.Message, current_user: dict):
    if not is_admin(current_user):
        await message.answer("⚠️ Perintah ini khusus untuk Admin.")
        return

    users = await list_users()
    if not users:
        await message.answer("Belum ada user yang terdaftar.")
        return

    lines = ["👥 *DAFTAR WHITELIST PENGGUNA BOT:* \n"]
    for u in users:
        status_ico = "🟢" if u['is_active'] else "🔴"
        uname = f"(@{u['username']})" if u.get('username') else ""
        lines.append(
            f"{status_ico} `{u['user_id']}` | *{u['full_name']}* {uname}\n"
            f"   Role: `{u['role']}` | Status: {'Aktif' if u['is_active'] else 'Nonaktif'}"
        )

    lines.append("\n💡 _Tambah user baru: `/adduser <telegram_id> <role> <nama>`_")
    lines.append("💡 _Ubah status: `/toggleuser <telegram_id>`_")
    await message.answer("\n".join(lines), parse_mode="Markdown")

@router.message(Command("adduser"))
async def cmd_adduser(message: types.Message, current_user: dict):
    if not is_admin(current_user):
        await message.answer("⚠️ Perintah ini khusus untuk Admin.")
        return

    # /adduser <telegram_id> <role> <nama...>
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        await message.answer(
            "ℹ️ *Format:* `/adduser <telegram_id> <role> <nama>`\n"
            "Role pilihan: `TEKNISI`, `SUPERVISOR`, `ADMIN`\n\n"
            "Contoh: `/adduser 123456789 TEKNISI Budi Santoso`",
            parse_mode="Markdown"
        )
        return

    raw_id = args[1].strip()
    role = args[2].strip().upper()
    name = args[3].strip()

    if not raw_id.isdigit():
        await message.answer("❌ Telegram ID harus berupa angka.")
        return

    if role not in ('TEKNISI', 'SUPERVISOR', 'ADMIN'):
        await message.answer("❌ Role tidak valid! Pilih: `TEKNISI`, `SUPERVISOR`, atau `ADMIN`.")
        return

    user_id = int(raw_id)
    user = await upsert_user(
        user_id=user_id,
        username="",
        full_name=name,
        role=role,
        is_active=1
    )

    await message.answer(
        f"✅ *Pengguna Berhasil Ditambahkan ke Whitelist!*\n\n"
        f"• *ID:* `{user['user_id']}`\n"
        f"• *Nama:* {user['full_name']}\n"
        f"• *Role:* `{user['role']}`\n"
        f"• *Status:* Aktif",
        parse_mode="Markdown"
    )

@router.message(Command("toggleuser"))
async def cmd_toggleuser(message: types.Message, current_user: dict):
    if not is_admin(current_user):
        await message.answer("⚠️ Perintah ini khusus untuk Admin.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.answer("ℹ️ *Format:* `/toggleuser <telegram_id>`", parse_mode="Markdown")
        return

    user_id = int(args[1].strip())
    from database.queries import get_user
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
    if not is_admin(current_user):
        await message.answer("⚠️ Perintah ini khusus untuk Admin.")
        return

    chat_id = message.chat.id
    await set_report_chat_id(chat_id)
    await message.answer(f"✅ Chat ID grup ini (`{chat_id}`) telah disimpan sebagai grup tim Pekanbaru.")
