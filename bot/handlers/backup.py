from aiogram import Router, F
from aiogram.types import Message
from db.models import UserRole
from services.backup_service import create_backup
import logging

router = Router()
logger = logging.getLogger("backup_handler")


def _is_admin(db_user) -> bool:
    return db_user and db_user.role in (UserRole.ADMIN, UserRole.SUPER)


@router.message(F.text == "💾 بکاپ")
async def manual_backup(msg: Message, db_user=None):
    if not _is_admin(db_user):
        await msg.answer("⛔️ دسترسی ندارید.")
        return
    wait_msg = await msg.answer("⏳ در حال ساخت بکاپ...")
    path = await create_backup(msg.bot)
    await wait_msg.delete()
    if path:
        import os
        size_mb = os.path.getsize(path) / (1024 * 1024)
        await msg.answer(f"✅ بکاپ ساخته شد.
📦 حجم: {size_mb:.2f} MB")
        with open(path, "rb") as f:
            await msg.answer_document(f, filename=os.path.basename(path))
    else:
        await msg.answer("❌ خطا در ساخت بکاپ. لاگ‌ها را بررسی کنید.")
