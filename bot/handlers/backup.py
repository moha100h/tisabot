from aiogram import Router, F
from aiogram.types import Message
from db.models import UserRole
import logging, os

router = Router()
logger = logging.getLogger("backup_handler")


def _is_admin(db_user):
    return db_user and db_user.role in (UserRole.ADMIN, UserRole.SUPER)


@router.message(F.text == "💾 بکاپ")
async def manual_backup(msg: Message, db_user=None):
    if not _is_admin(db_user):
        await msg.answer("⛔️ دسترسی ندارید.")
        return
    wait = await msg.answer("⏳ در حال ساخت بکاپ...")
    try:
        from services.backup import create_backup, send_backup
        path = await create_backup()
        size_mb = os.path.getsize(path) / (1024 * 1024)
        await wait.delete()
        with open(path, "rb") as f:
            await msg.answer_document(f, caption="✅ بکاپ آماده شد — " + f"{size_mb:.2f}" + " MB")
        await send_backup(msg.bot)
    except Exception as e:
        logger.error("backup error: %s", e)
        await wait.delete()
        await msg.answer("❌ خطا در ساخت بکاپ.")
