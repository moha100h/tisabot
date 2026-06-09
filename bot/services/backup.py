import os, tarfile, logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from db.database import AsyncSessionLocal
from db.repository import get_setting

logger = logging.getLogger("backup")
_scheduler: AsyncIOScheduler | None = None

BACKUP_DIR = os.getenv("BACKUP_DIR", "/app/backups")


async def create_backup() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    archive = os.path.join(BACKUP_DIR, "backup_" + ts + ".tar.gz")
    with tarfile.open(archive, "w:gz") as tar:
        media_dir = os.getenv("MEDIA_DIR", "/app/media")
        if os.path.exists(media_dir):
            tar.add(media_dir, arcname="media")
    pg_host = os.getenv("POSTGRES_HOST", "postgres")
    pg_port = os.getenv("POSTGRES_PORT", "5432")
    pg_user = os.getenv("POSTGRES_USER", "tisa")
    pg_pass = os.getenv("POSTGRES_PASSWORD", "")
    pg_db   = os.getenv("POSTGRES_DB", "tisabot")
    dump    = os.path.join(BACKUP_DIR, "db_" + ts + ".sql")
    ret = os.system(
        "PGPASSWORD='" + pg_pass + "' pg_dump"
        " -h " + pg_host + " -p " + pg_port +
        " -U " + pg_user + " " + pg_db +
        " > " + dump + " 2>/dev/null"
    )
    if ret == 0 and os.path.exists(dump):
        with tarfile.open(archive, "a:gz") as tar:
            tar.add(dump, arcname="db_" + ts + ".sql")
        os.remove(dump)
    size_mb = os.path.getsize(archive) / (1024 * 1024)
    logger.info("Backup created: %s (%.2f MB)", archive, size_mb)
    return archive


async def send_backup(bot: Bot) -> None:
    async with AsyncSessionLocal() as db:
        gid_str = await get_setting(db, "backup_group_id", "")
    gid = int(gid_str) if gid_str.lstrip("-").isdigit() else None
    if not gid:
        raise ValueError("backup_group_id تنظیم نشده — از پنل ادمین > تنظیمات ست کنید")
    path    = await create_backup()
    size_mb = os.path.getsize(path) / (1024 * 1024)
    ts_str  = datetime.now().strftime("%Y/%m/%d %H:%M")
    caption = (
        "💾 <b>بکاپ خودکار</b>\n"
        "📅 " + ts_str + "\n"
        "📦 " + f"{size_mb:.2f}" + " MB"
    )
    with open(path, "rb") as f:
        await bot.send_document(gid, f, caption=caption)
    logger.info("Backup sent to group %s (%.2f MB)", gid, size_mb)


def start_scheduler(bot: Bot, interval_hours: int = 6) -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(send_backup, "interval", hours=interval_hours,
                       args=[bot], id="auto_backup", replace_existing=True)
    _scheduler.start()
    logger.info("Backup scheduler started (every %dh)", interval_hours)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)