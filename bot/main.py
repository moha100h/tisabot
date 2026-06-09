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


async def main() -> None:
    storage = RedisStorage.from_url(REDIS_URL)
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=storage)

    # ── Middlewares ───────────────────────────────────────────
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # ── Routers (ترتیب مهم است) ───────────────────────────────
    dp.include_router(register_router)   # /start + FSM ثبت‌نام
    dp.include_router(backup_router)     # 💾 بکاپ
    dp.include_router(admin_router)      # /admin + پنل ادمین
    dp.include_router(listing_router)    # 🏠 ثبت آگهی
    dp.include_router(search_router)     # 🔍 جستجو
    dp.include_router(user_router)       # سایر دکمه‌های کاربری

    # ── Init DB ───────────────────────────────────────────────
    await init_db()
    await set_commands(bot)

    # ── Backup Scheduler ──────────────────────────────────────
    try:
        from services.backup_service import start_scheduler
        start_scheduler(bot, interval_hours=6)
        logger.info("Backup scheduler started (every 6h).")
    except Exception as e:
        logger.warning(f"Backup scheduler not started: {e}")

    logger.info(f"Bot started. ADMIN_ID={ADMIN_ID}")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
