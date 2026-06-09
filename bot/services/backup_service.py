import os, io, logging, tarfile
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from config import BACKUP_DIR

logger = logging.getLogger("backup")
_scheduler: AsyncIOScheduler | None = None


async def _get_backup_group(bot: Bot) -> int | None:
    """خواندن BACKUP_GROUP_ID از تنظیمات DB"""
    try:
        from db.database import AsyncSessionLocal
        from db.repository import get_setting
        async with AsyncSessionLocal() as db:
            val = await get_setting(db, "backup_group_id", "")
        return int(val) if val.lstrip("-").isdigit() else None
    except Exception:
        return None


async def create_backup(bot: Bot) -> str | None:
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = os.path.join(BACKUP_DIR, f"backup_{ts}.tar.gz")

        with tarfile.open(archive_path, "w:gz") as tar:
            media_dir = os.getenv("MEDIA_DIR", "/app/media")
            if os.path.exists(media_dir):
                tar.add(media_dir, arcname="media")

        pg_host = os.getenv("POSTGRES_HOST", "postgres")
        pg_port = os.getenv("POSTGRES_PORT", "5432")
        pg_user = os.getenv("POSTGRES_USER", "tisa")
        pg_pass = os.getenv("POSTGRES_PASSWORD", "")
        pg_db   = os.getenv("POSTGRES_DB", "tisabot")
        dump_path = os.path.join(BACKUP_DIR, f"db_{ts}.sql")

        ret = os.system(
            f"PGPASSWORD='{pg_pass}' pg_dump -h {pg_host} -p {pg_port} "
            f"-U {pg_user} {pg_db} > {dump_path} 2>/dev/null"
        )
        if ret == 0 and os.path.exists(dump_path):
            with tarfile.open(archive_path, "a:gz") as tar:
                tar.add(dump_path, arcname=f"db_{ts}.sql")
            os.remove(dump_path)

        size_mb = os.path.getsize(archive_path) / (1024 * 1024)
        logger.info(f"Backup created: {archive_path} ({size_mb:.2f} MB)")

        backup_group = await _get_backup_group(bot)
        if backup_group and bot:
            with open(archive_path, "rb") as f:
                await bot.send_document(
                    backup_group,
                    document=io.BufferedReader(f),
                    filename=f"backup_{ts}.tar.gz",
                    caption=(
                        f"💾 <b>بکاپ خودکار</b>
"
                        f"📅 {datetime.now().strftime('%Y/%m/%d %H:%M')}
"
                        f"📦 {size_mb:.2f} MB"
                    )
                )
        return archive_path
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return None


def start_scheduler(bot: Bot, interval_hours: int = 6) -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        create_backup, "interval", hours=interval_hours,
        args=[bot], id="auto_backup", replace_existing=True
    )
    _scheduler.start()
    logger.info(f"Backup scheduler started (every {interval_hours}h)")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
