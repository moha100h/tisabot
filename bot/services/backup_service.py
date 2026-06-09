# این فایل فقط برای سازگاری با import های قدیمی نگه داشته شده
# منطق اصلی در services/backup.py است
from services.backup import (
    create_backup,
    send_backup,
    start_scheduler,
    stop_scheduler,
    BACKUP_DIR,
)

__all__ = [
    "create_backup",
    "send_backup",
    "start_scheduler",
    "stop_scheduler",
    "BACKUP_DIR",
]
