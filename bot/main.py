import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

from config import BOT_TOKEN, ADMIN_ID, REDIS_URL
from db.database import init_db
from middlewares.auth import AuthMiddleware
from handlers.register import router as register_router
from handlers.user     import router as user_router
from handlers.listing  import router as listing_router
from handlers.search   import router as search_router
from handlers.admin    import router as admin_router
from handlers.backup   import router as backup_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")


async def set_commands(bot: Bot) -> None:
    base = [
        BotCommand(command="start",  description="شروع / منوی اصلی"),
        BotCommand(command="cancel", description="لغو عملیات جاری"),
    ]
    await bot.set_my_commands(base, scope=BotCommandScopeDefault())
    if ADMIN_ID:
        try:
            await bot.set_my_commands(
                base + [BotCommand(command="admin", description="پنل مدیریت")],
                scope=BotCommandScopeChat(chat_id=ADMIN_ID)
            )
        except Exception:
            pass


async def _ensure_admin() -> None:
    try:
        from db.database import AsyncSessionLocal
        from db.repository import get_user, create_user, update_user
        from db.models import UserRole
        async with AsyncSessionLocal() as db:
            admin = await get_user(db, ADMIN_ID)
            if not admin:
                admin = await create_user(
                    db,
                    telegram_id=ADMIN_ID,
                    full_name="Admin",
                    phone="0000000000",
                    username=None
                )
                logger.info("Admin %s created in DB.", ADMIN_ID)
            if admin.role != UserRole.SUPER:
                await update_user(db, ADMIN_ID, role=UserRole.SUPER)
                logger.info("Admin %s promoted to SUPER.", ADMIN_ID)
    except Exception as e:
        logger.warning("_ensure_admin failed: %s", e)


async def _get_backup_interval() -> int:
    try:
        from db.database import AsyncSessionLocal
        from db.repository import get_setting
        async with AsyncSessionLocal() as db:
            val = await get_setting(db, "backup_interval_hours", "6")
        return int(val) if val.isdigit() else 6
    except Exception:
        return 6


async def main() -> None:
    storage = RedisStorage.from_url(REDIS_URL)
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=storage)

    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    dp.include_router(register_router)
    dp.include_router(backup_router)
    dp.include_router(admin_router)
    dp.include_router(listing_router)
    dp.include_router(search_router)
    dp.include_router(user_router)

    await init_db()
    await set_commands(bot)
    await _ensure_admin()

    try:
        from services.backup import start_scheduler
        interval = await _get_backup_interval()
        start_scheduler(bot, interval_hours=interval)
        logger.info("Backup scheduler started (every %dh).", interval)
    except Exception as e:
        logger.warning("Backup scheduler not started: %s", e)

    logger.info("TisaBot started. ADMIN_ID=%s", ADMIN_ID)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())