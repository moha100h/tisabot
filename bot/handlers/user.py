from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from db.database import AsyncSessionLocal
from db.repository import (get_listing, list_listings, list_consultants,
    get_setting, update_listing, delete_listing)
from db.models import ListingStatus
from keyboards.main import main_menu, my_listing_status_kb, listing_card_kb
import logging

router = Router()
logger = logging.getLogger("user")


def _fmt_listing(lst, show_phone: bool = False) -> str:
    TYPE_MAP = {"sale": "فروش", "rent": "رهن/اجاره", "partnership": "مشارکت"}
    PROP_MAP = {"apartment": "آپارتمان", "villa": "ویلا", "commercial": "تجاری",
                "land": "زمین", "office": "دفتر", "other": "سایر"}
    STATUS_MAP = {"pending": "⏳ در انتظار تأیید", "approved": "✅ تأیید شده",
                  "rejected": "❌ رد شده", "available": "🟢 موجود",
                  "sold": "💰 فروخته شد", "rented": "🏠 اجاره رفت",
                  "mortgaged": "🔑 رهن رفت", "inactive": "⏸ غیرفعال"}
    lines = [
        f"🏷 <b>کد ملک:</b> {lst.code}",
        f"📌 <b>نوع معامله:</b> {TYPE_MAP.get(lst.listing_type.value, lst.listing_type.value)}",
        f"🏠 <b>نوع ملک:</b> {PROP_MAP.get(lst.property_type.value, lst.property_type.value)}",
        f"📍 <b>موقعیت:</b> {lst.province} — {lst.city}" + (f" — {lst.district}" if lst.district else ""),
    ]
    if lst.area:      lines.append(f"📐 <b>متراژ:</b> {lst.area:,} متر")
    if lst.bedrooms:  lines.append(f"🛏 <b>اتاق:</b> {lst.bedrooms}")
    if lst.price:     lines.append(f"💵 <b>قیمت:</b> {lst.price:,} تومان")
    if lst.mortgage:  lines.append(f"🔑 <b>رهن:</b> {lst.mortgage:,} تومان")
    if lst.rent:      lines.append(f"🏠 <b>اجاره:</b> {lst.rent:,} تومان")
    if lst.description: lines.append(f"📝 <b>توضیحات:</b> {lst.description}")
    lines.append(f"📊 <b>وضعیت:</b> {STATUS_MAP.get(lst.status.value, lst.status.value)}")
    if lst.rejection_reason:
        lines.append(f"⚠️ <b>دلیل رد:</b> {lst.rejection_reason}")
    return "
".join(lines)


# ── آگهی‌های من ───────────────────────────────────────────────
@router.message(F.text == "📋 آگهی‌های من")
async def my_listings(msg: Message, db_user=None):
    if not db_user:
        await msg.answer("⚠️ ابتدا ثبت‌نام کنید. /start")
        return
    async with AsyncSessionLocal() as db:
        listings = await list_listings(db, owner_id=db_user.telegram_id)
    if not listings:
        await msg.answer("📭 هنوز آگهی ثبت نکرده‌اید.")
        return
    for lst in listings[:10]:
        text = _fmt_listing(lst)
        kb = my_listing_status_kb(lst.id)
        if lst.images:
            await msg.answer_photo(lst.images[0].file_id, caption=text, reply_markup=kb)
        else:
            await msg.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("setstatus:"))
async def set_listing_status(cb: CallbackQuery, db_user=None):
    _, lid, status = cb.data.split(":")
    async with AsyncSessionLocal() as db:
        lst = await get_listing(db, int(lid))
        if not lst or lst.owner_id != db_user.telegram_id:
            await cb.answer("⛔️ دسترسی ندارید.", show_alert=True)
            return
        await update_listing(db, int(lid), status=ListingStatus(status))
    await cb.answer("✅ وضعیت آگهی به‌روز شد.")
    await cb.message.delete()


@router.callback_query(F.data.startswith("del_lst:"))
async def delete_listing_cb(cb: CallbackQuery, db_user=None):
    lid = int(cb.data.split(":")[1])
    async with AsyncSessionLocal() as db:
        lst = await get_listing(db, lid)
        if not lst or lst.owner_id != db_user.telegram_id:
            await cb.answer("⛔️ دسترسی ندارید.", show_alert=True)
            return
        await delete_listing(db, lid)
    await cb.answer("🗑 آگهی حذف شد.")
    await cb.message.delete()


# ── مشاوران ───────────────────────────────────────────────────
@router.message(F.text == "👥 مشاوران")
async def show_consultants(msg: Message):
    async with AsyncSessionLocal() as db:
        consultants = await list_consultants(db)
    if not consultants:
        await msg.answer("📭 مشاوری ثبت نشده است.")
        return
    for c in consultants:
        lines = [f"👨‍💼 <b>{c.name}</b>"]
        if c.phone:         lines.append(f"📞 {c.phone}")
        if c.telegram:      lines.append(f"💬 @{c.telegram}")
        if c.working_hours: lines.append(f"🕐 {c.working_hours}")
        if c.office:        lines.append(f"📍 {c.office}")
        await msg.answer("
".join(lines))


# ── تماس با ما ────────────────────────────────────────────────
@router.message(F.text == "📞 تماس با ما")
async def contact_us(msg: Message):
    async with AsyncSessionLocal() as db:
        text = await get_setting(db, "contact_info", "اطلاعات تماس ثبت نشده است.")
    await msg.answer(text)


# ── درباره ما ─────────────────────────────────────────────────
@router.message(F.text == "ℹ️ درباره ما")
async def about_us(msg: Message):
    async with AsyncSessionLocal() as db:
        text = await get_setting(db, "about_us", "اطلاعاتی ثبت نشده است.")
    await msg.answer(text)


# ── مشاوره تلگرامی ───────────────────────────────────────────
@router.callback_query(F.data.startswith("consult:"))
async def consult_request(cb: CallbackQuery, db_user=None):
    lid = int(cb.data.split(":")[1])
    async with AsyncSessionLocal() as db:
        lst = await get_listing(db, lid)
        consultants = await list_consultants(db)
    if not lst:
        await cb.answer("آگهی یافت نشد.", show_alert=True)
        return
    text = (
        f"📩 <b>درخواست مشاوره</b>

"
        f"🏷 کد ملک: {lst.code}
"
        f"📍 {lst.province} — {lst.city}
"
        f"👤 متقاضی: {db_user.full_name if db_user else 'ناشناس'}
"
        f"📞 تلفن: {db_user.phone if db_user else '—'}"
    )
    for c in consultants:
        if c.telegram:
            try:
                await cb.bot.send_message(f"@{c.telegram}", text)
            except Exception:
                pass
    await cb.answer("✅ درخواست مشاوره ارسال شد.", show_alert=True)
