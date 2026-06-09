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
STATUS_MAP = {
    "pending":   "⏳ در انتظار بررسی",
    "approved":  "✅ تأیید شده",
    "rejected":  "❌ رد شده",
    "available": "🟢 موجود",
    "sold":      "🔴 فروخته شده",
    "rented":    "🔵 اجاره رفته",
    "mortgaged": "🔑 رهن رفته",
    "inactive":  "⚫️ غیرفعال",
}


def _owner_card(lst) -> str:
    lines = ["🏷 کد: <code>" + lst.code + "</code>"]
    lines.append("📌 " + TYPE_MAP.get(lst.listing_type.value, "") + " — " + PROP_MAP.get(lst.property_type.value, ""))
    lines.append("📍 " + lst.province + " — " + lst.city)
    if lst.district:      lines.append("🏘 محله: " + lst.district)
    if lst.address:       lines.append("📍 آدرس: " + lst.address)
    if lst.area:          lines.append("📐 متراژ: " + str(lst.area) + " متر")
    if lst.bedrooms:      lines.append("🛏 اتاق: " + str(lst.bedrooms))
    if lst.price:         lines.append("💵 قیمت: " + f"{lst.price:,}" + " تومان")
    if lst.mortgage:      lines.append("🔑 رهن: " + f"{lst.mortgage:,}" + " تومان")
    if lst.rent:          lines.append("🏠 اجاره: " + f"{lst.rent:,}" + " تومان")
    if lst.facilities:    lines.append("🏊 امکانات: " + lst.facilities)
    if lst.description:   lines.append("📝 " + lst.description)
    if lst.contact_phone: lines.append("📞 تماس بازدید: " + lst.contact_phone)
    lines.append("📊 وضعیت: " + STATUS_MAP.get(lst.status.value, lst.status.value))
    if lst.rejection_reason: lines.append("⚠️ دلیل رد: " + lst.rejection_reason)
    return "\n".join(lines)


@router.message(F.text.in_({"📋 آگهی‌های من", "🏠 آگهی‌های من"}))
async def my_listings(msg: Message, db_user=None):
    if not db_user:
        await msg.answer("⚠️ ابتدا ثبت‌نام کنید. /start")
        return
    async with AsyncSessionLocal() as db:
        listings = await list_listings(db, owner_id=db_user.telegram_id, limit=20)
    if not listings:
        await msg.answer("📭 هنوز آگهی ثبت نکرده‌اید.")
        return
    await msg.answer("📋 <b>آگهی‌های شما " + "(" + str(len(listings)) + " مورد):</b>")
    for lst in listings:
        b = InlineKeyboardBuilder()
        if lst.status.value in ("approved", "available"):
            b.button(text="⏸ غیرفعال کردن", callback_data="ulst:inactive:" + str(lst.id))
        elif lst.status.value == "inactive":
            b.button(text="▶️ فعال کردن",   callback_data="ulst:available:" + str(lst.id))
        b.button(text="🗑 حذف آگهی", callback_data="ulst:delete:" + str(lst.id))
        b.adjust(1)
        card = _owner_card(lst)
        if lst.images:
            await msg.answer_photo(lst.images[0].file_id, caption=card, reply_markup=b.as_markup())
        else:
            await msg.answer(card, reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("ulst:"))
async def listing_action(cb: CallbackQuery, db_user=None):
    parts  = cb.data.split(":")
    action = parts[1]
    lid    = int(parts[2])
    async with AsyncSessionLocal() as db:
        if action == "delete":
            await delete_listing(db, lid)
            await cb.answer("🗑 آگهی حذف شد.", show_alert=True)
            await cb.message.delete()
        else:
            await update_listing(db, lid, status=ListingStatus(action))
            label = "⏸ غیرفعال شد" if action == "inactive" else "▶️ فعال شد"
            await cb.answer(label, show_alert=True)
            await cb.message.delete()


@router.message(F.text.in_({"👨‍💼 مشاوران", "👥 مشاوران"}))
async def show_consultants(msg: Message):
    async with AsyncSessionLocal() as db:
        consultants = await list_consultants(db)
    if not consultants:
        await msg.answer("📭 مشاوری ثبت نشده است.")
        return
    for c in consultants:
        text = "👤 <b>" + c.name + "</b>\n📞 " + c.phone
        if c.telegram:      text += "\n💬 @" + c.telegram
        if c.working_hours: text += "\n🕐 " + c.working_hours
        await msg.answer(text)


@router.message(F.text == "📞 تماس با ما")
async def contact_us(msg: Message):
    async with AsyncSessionLocal() as db:
        text = await get_setting(db, "contact_info", "")
    await msg.answer(text if text else "اطلاعات تماس هنوز ثبت نشده است.")


@router.message(F.text == "ℹ️ درباره ما")
async def about_us(msg: Message):
    async with AsyncSessionLocal() as db:
        text = await get_setting(db, "about_us", "")
    await msg.answer(text if text else "اطلاعات درباره ما هنوز ثبت نشده است.")


@router.message(F.text == "📋 قوانین")
async def rules(msg: Message):
    async with AsyncSessionLocal() as db:
        text = await get_setting(db, "rules", "")
    await msg.answer(text if text else "قوانین هنوز ثبت نشده است.")


@router.message(F.text == "/cancel")
async def cancel_any(msg: Message, state=None):
    if state:
        await state.clear()
    await msg.answer("❌ عملیات لغو شد.", reply_markup=main_menu())