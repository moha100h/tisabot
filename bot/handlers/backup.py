from aiogram import Router, F
from aiogram.types import Message
from db.database import AsyncSessionLocal
from db.repository import get_setting
from db.models import UserRole
import logging

router = Router()
logger = logging.getLogger("backup_handler")


def _is_admin(db_user) -> bool:
    return db_user and db_user.role in (UserRole.ADMIN, UserRole.SUPER)


@router.message(F.text == "💾 بکاپ")
async def manual_backup(msg: Message, db_user=None):
    if not _is_admin(db_user):
        await msg.answer("⛔ دسترسی ندارید.")
        return
    await msg.answer("⏳ در حال ساخت بکاپ...")
    try:
        from services.backup import send_backup
        await send_backup(msg.bot)
        await msg.answer("✅ بکاپ ساخته و ارسال شد.")
    except Exception as e:
        await msg.answer("❌ خطا: " + str(e))
        logger.error("manual backup: %s", e)