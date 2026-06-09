from aiogram import Router, F
from aiogram.types import Message
from db.database import AsyncSessionLocal
from db.repository import get_user
from db.models import UserRole
from services.backup import create_backup, send_backup
import logging, os

router = Router()
logger = logging.getLogger("backup_handler")


def _is_admin(db_user) -> bool:
    return db_user and db_user.role in (UserRole.ADMIN, UserRole.SUPER)


@router.message(F.text == "💾 بکاپ")
async def manual_backup(msg: Message, db_user=None):
    if not _is_admin(db_user):
        await msg.answer("⛔️ دسترسی ندارید.")
        return
    await msg.answer("⏳ در حال ساخت بکاپ...")
    try:
        path = await create_backup()
        size_mb = os.path.getsize(path) / (1024 * 1024)
        with open(path, "rb") as f:
            await msg.answer_document(f,
                caption=f"✅ بکاپ آماده شد
📦 حجم: {size_mb:.2f} MB")
        # ارسال به گروه بکاپ هم
        await send_backup(msg.bot)
    except Exception as e:
        logger.error(f"Manual backup error: {e}")
        await msg.answer(f"❌ خطا در ساخت بکاپ:
<code>{e}</code>")
