import os

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Check your .env file.")

_admin_raw = os.getenv("ADMIN_ID", "")
ADMIN_ID: int = int(_admin_raw) if _admin_raw.isdigit() else 0
if not ADMIN_ID:
    raise RuntimeError("ADMIN_ID is not set. Check your .env file.")

POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER: str = os.getenv("POSTGRES_USER", "tisa")
POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_DB: str = os.getenv("POSTGRES_DB", "tisabot")

REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")

MEDIA_DIR:  str = os.getenv("MEDIA_DIR",  "/app/media")
BACKUP_DIR: str = os.getenv("BACKUP_DIR", "/app/backups")

for _d in [MEDIA_DIR, BACKUP_DIR]:
    os.makedirs(_d, exist_ok=True)

# همه تنظیمات دیگر (REVIEW_GROUP_ID، BACKUP_GROUP_ID، ...) از DB خوانده می‌شوند
