from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from config import ADMIN_IDS
from database.queries import get_user, upsert_user

class WhitelistMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        user_id = user.id

        # Auto-whitelist configured bootstrap admins
        if user_id in ADMIN_IDS:
            db_user = await get_user(user_id)
            if not db_user or db_user['role'] != 'ADMIN' or not db_user['is_active']:
                db_user = await upsert_user(
                    user_id=user_id,
                    username=user.username or "",
                    full_name=user.full_name or f"User {user_id}",
                    role='ADMIN',
                    is_active=1
                )
            data["current_user"] = db_user
            return await handler(event, data)

        db_user = await get_user(user_id)

        if not db_user or not db_user.get("is_active"):
            msg_text = (
                f"⛔ *Akses Ditolak*\n\n"
                f"Halo {user.full_name},\n"
                f"Akun Anda belum terdaftar di whitelist Bot Broadband Fiberstar (Tim Pekanbaru).\n\n"
                f"Silakan berikan Telegram ID Anda ke Admin Medan:\n"
                f"🆔 *User ID Anda:* `{user_id}`"
            )
            if isinstance(event, Message):
                await event.answer(msg_text, parse_mode="Markdown")
            elif isinstance(event, CallbackQuery):
                await event.answer("Akses ditolak: Akun belum terdaftar di whitelist.", show_alert=True)
            return

        data["current_user"] = db_user
        return await handler(event, data)
