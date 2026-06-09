from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.database import AsyncSessionLocal
from db.repository import list_listings, update_listing, delete_listing, list_consultants, get_setting
from db.models import ListingStatus
from keyboards.main import main_menu
import logging

router = Router()
logger = logging.getLogger("user")

TYPE_MAP = {"sale": "فروش", "rent": "رهن/اجاره", "partnership": "مشارکت"}
PROP_MAP = {"apartment": "آپارتمان", "villa": "ویلا", "commercial": "تجاری",
            "land": "زمین", "office": "دفتر", "other": "سایر"}
STATUS_MAP = {"pending": "⏳ در انتظار", "approved": "✅ تأیید", "rejected": "❌ رد",
              "available": "🟢 موجود", "sold": "🔴 فروخته", "rented": "🔵 اجاره", "inactive": "⚫️ غیرفعال"}


def _card(lst):
    lines = ["🏷 کد: <code>" + lst.code + "</code>"]
    lines.append("📌 " + TYPE_MAP.get(lst.listing_type.value, "") + " — " + PROP_MAP.get(lst.property_type.value, ""))
    lines.append("📍 " + lst.province + " — " + lst.city)
    if lst.area:     lines.append("📐 " + str(lst.area) + " متر")
    if lst.price:    lines.append("💵 " + f"{lst.price:,}" + " تومان")
    if lst.mortgage: lines.append("🔑 رهن: " + f"{lst.mortgage:,}" + " تومان")
    if lst.rent:     lines.append("🏠 اجاره: " + f"{lst.rent:,}" + " تومان")
    lines.append("📊 " + STATUS_MAP.get(lst.status.value, lst.status.value))
    if lst.rejection_reason: lines.append("⚠️ دلیل رد: " + lst.rejection_reason)
    return "\n".join(lines)


@router.message(F.text == "🏠 آگهی‌های من")
async def my_listings(msg: Message, db_user=None):
    if not db_user:
        await msg.answer("⚠️ ابتدا ثبت‌نام کنید. /start")
        return
    async with AsyncSessionLocal() as db:
        listings = await list_listings(db, owner_id=db_user.telegram_id, limit=10)
    if not listings:
        await msg.answer("📭 هنوز آگهی ثبت نکرده‌اید.")
        return
    for lst in listings:
        b = InlineKeyboardBuilder()
        if lst.status.value in ("approved", "available"):
            b.button(text="🔴 غیرفعال", callback_data="ulst:inactive:" + str(lst.id))
        elif lst.status.value == "inactive":
            b.button(text="🟢 فعال",    callback_data="ulst:available:" + str(lst.id))
        b.button(text="🗑 حذف", callback_data="ulst:delete:" + str(lst.id))
        b.adjust(2)
        if lst.images:
            await msg.answer_photo(lst.images[0].file_id, caption=_card(lst), reply_markup=b.as_markup())
        else:
            await msg.answer(_card(lst), reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("ulst:"))
async def listing_action(cb: CallbackQuery, db_user=None):
    parts  = cb.data.split(":")
    action = parts[1]
    lid    = int(parts[2])
    async with AsyncSessionLocal() as db:
        if action == "delete":
            await delete_listing(db, lid)
            await cb.answer("🗑 حذف شد.")
        else:
            await update_listing(db, lid, status=ListingStatus(action))
            await cb.answer("✅ وضعیت تغییر کرد.")
    await cb.message.delete()


@router.message(F.text == "👨‍💼 مشاوران")
async def show_consultants(msg: Message):
    async with AsyncSessionLocal() as db:
        consultants = await list_consultants(db)
    if not consultants:
        await msg.answer("📭 مشاوری ثبت نشده است.")
        return
    for c in consultants:
        text = "👤 <b>" + c.name + "</b>\n📞 " + c.phone
        if c.telegram:     text += "\n💬 @" + c.telegram
        if c.working_hours: text += "\n🕐 " + c.working_hours
        await msg.answer(text)


@router.message(F.text == "📞 تماس با ما")
async def contact_us(msg: Message):
    async with AsyncSessionLocal() as db:
        text = await get_setting(db, "contact_info", "اطلاعات تماس ثبت نشده است.")
    await msg.answer(text)


@router.message(F.text == "ℹ️ درباره ما")
async def about_us(msg: Message):
    async with AsyncSessionLocal() as db:
        text = await get_setting(db, "about_us", "اطلاعات درباره ما ثبت نشده است.")
    await msg.answer(text)


@router.message(F.text == "📋 قوانین")
async def rules(msg: Message):
    async with AsyncSessionLocal() as db:
        text = await get_setting(db, "rules", "قوانین ثبت نشده است.")
    await msg.answer(text)
