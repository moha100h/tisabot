import os, io, tarfile, logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from db.database import AsyncSessionLocal
from db.repository import get_setting

logger = logging.getLogger("backup")
_scheduler: AsyncIOScheduler | None = None


async def create_backup() -> str:
    """ساخت فایل tar.gz از پوشه‌های media و data"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.getenv("BACKUP_DIR", "/app/backups")
    os.makedirs(backup_dir, exist_ok=True)
    out_path = os.path.join(backup_dir, f"backup_{ts}.tar.gz")

    dirs_to_backup = [
        os.getenv("MEDIA_DIR", "/app/media"),
    ]
    with tarfile.open(out_path, "w:gz") as tar:
        for d in dirs_to_backup:
            if os.path.exists(d):
                tar.add(d, arcname=os.path.basename(d))
    logger.info(f"Backup created: {out_path} ({os.path.getsize(out_path)} bytes)")
    return out_path


async def send_backup(bot: Bot) -> None:
    async with AsyncSessionLocal() as db:
        group_id_str = await get_setting(db, "backup_group_id", "")

    from config import BACKUP_GROUP_ID
    group_id = int(group_id_str) if group_id_str.lstrip("-").isdigit() else BACKUP_GROUP_ID
    if not group_id:
        logger.warning("BACKUP_GROUP_ID not set — skipping backup send.")
        return

    try:
        path = await create_backup()
        size_mb = os.path.getsize(path) / (1024 * 1024)
        caption = (
            f"💾 <b>بکاپ خودکار</b>
"
            f"📅 {datetime.now().strftime('%Y/%m/%d %H:%M')}
"
            f"📦 حجم: {size_mb:.2f} MB"
        )
        with open(path, "rb") as f:
            await bot.send_document(group_id, f, caption=caption)
        logger.info(f"Backup sent to group {group_id}")
    except Exception as e:
        logger.error(f"Backup failed: {e}")


def start_scheduler(bot: Bot) -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(send_backup, "interval", hours=6, args=[bot],
                       id="auto_backup", replace_existing=True)
    _scheduler.start()
    logger.info("Backup scheduler started (every 6h).")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
