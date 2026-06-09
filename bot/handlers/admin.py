from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.database import AsyncSessionLocal
from db.repository import (
    get_user, update_user, list_users, count_users, search_users,
    list_listings, get_listing, update_listing, delete_listing,
    list_consultants, create_consultant, delete_consultant,
    get_setting, set_setting,
)
from db.models import UserRole, ListingStatus
from keyboards.main import admin_menu, main_menu, review_group_kb
from config import ADMIN_ID
import logging

router = Router()
logger = logging.getLogger("admin")

TYPE_MAP = {"sale": "فروش", "rent": "رهن/اجاره", "partnership": "مشارکت"}
PROP_MAP = {"apartment": "آپارتمان", "villa": "ویلا", "commercial": "تجاری",
            "land": "زمین", "office": "دفتر", "other": "سایر"}
STATUS_MAP = {
    "pending":   "⏳ در انتظار",
    "approved":  "✅ تأیید",
    "rejected":  "❌ رد",
    "available": "🟢 موجود",
    "sold":      "🔴 فروخته",
    "rented":    "🔵 اجاره",
    "mortgaged": "🔑 رهن",
    "inactive":  "⚫️ غیرفعال",
}


def _is_admin(db_user) -> bool:
    return db_user and db_user.role in (UserRole.ADMIN, UserRole.SUPER)


def _admin_card(lst) -> str:
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
    if lst.owner:
        lines.append("👤 مالک: " + lst.owner.full_name + " | " + lst.owner.phone)
    lines.append("📊 وضعیت: " + STATUS_MAP.get(lst.status.value, lst.status.value))
    if lst.rejection_reason: lines.append("⚠️ دلیل رد: " + lst.rejection_reason)
    return "\n".join(lines)


# ── FSM ──────────────────────────────────────────────────
class AdminFSM(StatesGroup):
    reject_reason    = State()
    broadcast_text   = State()
    setting_key      = State()
    setting_value    = State()
    consultant_name  = State()
    consultant_phone = State()
    consultant_tg    = State()
    consultant_hours = State()


# ── ورود به پنل ──────────────────────────────────────────
@router.message(F.text == "/admin")
async def admin_panel(msg: Message, db_user=None):
    if not _is_admin(db_user):
        await msg.answer("⛔ دسترسی ندارید.")
        return
    await msg.answer("⚙️ <b>پنل مدیریت</b>", reply_markup=admin_menu())


@router.message(F.text == "🔙 خروج از پنل ادمین")
async def exit_admin(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("✅ از پنل خارج شدید.", reply_markup=main_menu())


# ── مدیریت آگهی‌ها ───────────────────────────────────────
@router.message(F.text == "📋 مدیریت آگهی‌ها")
async def manage_listings(msg: Message, db_user=None):
    if not _is_admin(db_user): return
    b = InlineKeyboardBuilder()
    for label, val in [
        ("⏳ در انتظار", "pending"),
        ("✅ تأیید شده", "approved"),
        ("❌ رد شده",   "rejected"),
        ("📋 همه",      "all"),
    ]:
        b.button(text=label, callback_data="lstf:" + val)
    b.adjust(2)
    await msg.answer("📋 فیلتر آگهی‌ها:", reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("lstf:"))
async def listing_filter(cb: CallbackQuery, db_user=None):
    if not _is_admin(db_user):
        await cb.answer("⛔", show_alert=True)
        return
    val = cb.data.split(":")[1]
    status = None if val == "all" else ListingStatus(val)
    async with AsyncSessionLocal() as db:
        listings = await list_listings(db, status=status, limit=20)
    await cb.message.delete()
    if not listings:
        await cb.message.answer("📭 آگهی‌ای یافت نشد.")
        return
    await cb.message.answer("📋 <b>" + str(len(listings)) + " آگهی:</b>")
    for lst in listings:
        b = InlineKeyboardBuilder()
        if lst.status.value == "pending":
            b.button(text="✅ تأیید", callback_data="rev:approve:" + str(lst.id))
            b.button(text="❌ رد",    callback_data="rev:reject:"  + str(lst.id))
        b.button(text="🗑 حذف", callback_data="adm:del:" + str(lst.id))
        b.adjust(2, 1)
        card = _admin_card(lst)
        if lst.images:
            await cb.message.answer_photo(lst.images[0].file_id, caption=card, reply_markup=b.as_markup())
        else:
            await cb.message.answer(card, reply_markup=b.as_markup())


# ── تأیید / رد آگهی (از گروه بازبینی یا پنل) ────────────
@router.callback_query(F.data.startswith("rev:"))
async def review_action(cb: CallbackQuery, state: FSMContext, db_user=None):
    if not _is_admin(db_user):
        await cb.answer("⛔", show_alert=True)
        return
    parts  = cb.data.split(":")
    action = parts[1]
    lid    = int(parts[2])
    if action == "approve":
        async with AsyncSessionLocal() as db:
            lst = await get_listing(db, lid)
            if not lst:
                await cb.answer("آگهی یافت نشد.", show_alert=True)
                return
            await update_listing(db, lid, status=ListingStatus.APPROVED)
            owner_id = lst.owner_id
            code     = lst.code
        await cb.answer("✅ تأیید شد.", show_alert=True)
        await cb.message.edit_reply_markup(reply_markup=None)
        try:
            await cb.bot.send_message(
                owner_id,
                "✅ <b>آگهی شما تأیید شد!</b>\n"
                "🏷 کد: <code>" + code + "</code>\n"
                "آگهی شما منتشر شده است."
            )
        except Exception:
            pass
    else:
        await state.update_data(review_lid=lid, review_msg_id=cb.message.message_id,
                                review_chat_id=cb.message.chat.id)
        await state.set_state(AdminFSM.reject_reason)
        await cb.message.answer("✏️ دلیل رد را بنویسید:")
        await cb.answer()


@router.message(AdminFSM.reject_reason, F.text)
async def got_reject_reason(msg: Message, state: FSMContext):
    data   = await state.get_data()
    lid    = data["review_lid"]
    reason = msg.text.strip()
    await state.clear()
    async with AsyncSessionLocal() as db:
        lst = await get_listing(db, lid)
        if not lst:
            await msg.answer("آگهی یافت نشد.")
            return
        await update_listing(db, lid, status=ListingStatus.REJECTED, rejection_reason=reason)
        owner_id = lst.owner_id
        code     = lst.code
    await msg.answer("❌ آگهی رد شد.")
    try:
        await msg.bot.send_message(
            owner_id,
            "❌ <b>آگهی شما رد شد.</b>\n"
            "🏷 کد: <code>" + code + "</code>\n"
            "⚠️ دلیل: " + reason
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm:del:"))
async def admin_del_listing(cb: CallbackQuery, db_user=None):
    if not _is_admin(db_user):
        await cb.answer("⛔", show_alert=True)
        return
    lid = int(cb.data.split(":")[2])
    async with AsyncSessionLocal() as db:
        await delete_listing(db, lid)
    await cb.answer("🗑 حذف شد.", show_alert=True)
    await cb.message.delete()


# ── مدیریت کاربران ───────────────────────────────────────
@router.message(F.text == "👥 مدیریت کاربران")
async def manage_users(msg: Message, db_user=None):
    if not _is_admin(db_user): return
    async with AsyncSessionLocal() as db:
        total = await count_users(db)
        users = await list_users(db, limit=10)
    text = "👥 <b>کاربران (" + str(total) + " نفر)</b>\n\n"
    for u in users:
        role_icon = "👑" if u.role == UserRole.SUPER else ("🔧" if u.role == UserRole.ADMIN else "👤")
        blocked   = " 🚫" if u.is_blocked else ""
        text += role_icon + " " + u.full_name + " | " + u.phone + blocked + "\n"
    b = InlineKeyboardBuilder()
    b.button(text="🔍 جستجوی کاربر", callback_data="usr:search")
    await msg.answer(text, reply_markup=b.as_markup())


@router.callback_query(F.data == "usr:search")
async def usr_search_start(cb: CallbackQuery, state: FSMContext, db_user=None):
    if not _is_admin(db_user): return
    await state.set_state(AdminFSM.setting_key)
    await cb.message.answer("🔍 نام، شماره یا یوزرنیم کاربر را وارد کنید:")
    await cb.answer()


@router.message(AdminFSM.setting_key, F.text)
async def usr_search_result(msg: Message, state: FSMContext):
    await state.clear()
    async with AsyncSessionLocal() as db:
        users = await search_users(db, msg.text.strip())
    if not users:
        await msg.answer("📭 کاربری یافت نشد.")
        return
    for u in users:
        b = InlineKeyboardBuilder()
        b.button(text="🚫 بلاک" if not u.is_blocked else "✅ آنبلاک",
                 callback_data="usr:block:" + str(u.telegram_id))
        b.button(text="🔧 ادمین" if u.role == UserRole.USER else "👤 کاربر عادی",
                 callback_data="usr:role:" + str(u.telegram_id))
        b.adjust(2)
        role_icon = "👑" if u.role == UserRole.SUPER else ("🔧" if u.role == UserRole.ADMIN else "👤")
        text = (role_icon + " <b>" + u.full_name + "</b>\n"
                "📞 " + u.phone + "\n"
                + ("@" + u.username + "\n" if u.username else ""))
        await msg.answer(text, reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("usr:block:"))
async def toggle_block(cb: CallbackQuery, db_user=None):
    if not _is_admin(db_user): return
    tid = int(cb.data.split(":")[2])
    async with AsyncSessionLocal() as db:
        u = await get_user(db, tid)
        if u:
            await update_user(db, tid, is_blocked=not u.is_blocked)
            label = "✅ آنبلاک شد" if u.is_blocked else "🚫 بلاک شد"
            await cb.answer(label, show_alert=True)
    await cb.message.delete()


@router.callback_query(F.data.startswith("usr:role:"))
async def toggle_role(cb: CallbackQuery, db_user=None):
    if not _is_admin(db_user): return
    tid = int(cb.data.split(":")[2])
    async with AsyncSessionLocal() as db:
        u = await get_user(db, tid)
        if u and u.role != UserRole.SUPER:
            new_role = UserRole.USER if u.role == UserRole.ADMIN else UserRole.ADMIN
            await update_user(db, tid, role=new_role)
            await cb.answer("نقش تغییر کرد.", show_alert=True)
    await cb.message.delete()


# ── مشاوران ──────────────────────────────────────────────
@router.message(F.text == "👨‍💼 مشاوران")
async def admin_consultants(msg: Message, db_user=None):
    if not _is_admin(db_user): return
    async with AsyncSessionLocal() as db:
        consultants = await list_consultants(db)
    b = InlineKeyboardBuilder()
    b.button(text="➕ افزودن مشاور", callback_data="cons:add")
    if consultants:
        for c in consultants:
            b.button(text="🗑 " + c.name, callback_data="cons:del:" + str(c.id))
    b.adjust(1)
    text = "👨‍💼 <b>مشاوران (" + str(len(consultants)) + " نفر)</b>"
    await msg.answer(text, reply_markup=b.as_markup())


@router.callback_query(F.data == "cons:add")
async def cons_add_start(cb: CallbackQuery, state: FSMContext, db_user=None):
    if not _is_admin(db_user): return
    await state.set_state(AdminFSM.consultant_name)
    await cb.message.answer("👤 نام مشاور:")
    await cb.answer()


@router.message(AdminFSM.consultant_name, F.text)
async def cons_name(msg: Message, state: FSMContext):
    await state.update_data(cons_name=msg.text.strip())
    await state.set_state(AdminFSM.consultant_phone)
    await msg.answer("📞 شماره تماس:")


@router.message(AdminFSM.consultant_phone, F.text)
async def cons_phone(msg: Message, state: FSMContext):
    await state.update_data(cons_phone=msg.text.strip())
    await state.set_state(AdminFSM.consultant_tg)
    b = InlineKeyboardBuilder()
    b.button(text="⏭ رد کردن", callback_data="skip_cons_tg")
    await msg.answer("💬 یوزرنیم تلگرام (بدون @):", reply_markup=b.as_markup())


@router.callback_query(AdminFSM.consultant_tg, F.data == "skip_cons_tg")
async def skip_cons_tg(cb: CallbackQuery, state: FSMContext):
    await state.update_data(cons_tg=None)
    await state.set_state(AdminFSM.consultant_hours)
    b = InlineKeyboardBuilder()
    b.button(text="⏭ رد کردن", callback_data="skip_cons_hours")
    await cb.message.edit_text("🕐 ساعت کاری:", reply_markup=b.as_markup())


@router.message(AdminFSM.consultant_tg, F.text)
async def cons_tg(msg: Message, state: FSMContext):
    await state.update_data(cons_tg=msg.text.strip().lstrip("@"))
    await state.set_state(AdminFSM.consultant_hours)
    b = InlineKeyboardBuilder()
    b.button(text="⏭ رد کردن", callback_data="skip_cons_hours")
    await msg.answer("🕐 ساعت کاری:", reply_markup=b.as_markup())


@router.callback_query(AdminFSM.consultant_hours, F.data == "skip_cons_hours")
async def skip_cons_hours(cb: CallbackQuery, state: FSMContext):
    await state.update_data(cons_hours=None)
    await _save_consultant(cb.message, state)


@router.message(AdminFSM.consultant_hours, F.text)
async def cons_hours(msg: Message, state: FSMContext):
    await state.update_data(cons_hours=msg.text.strip())
    await _save_consultant(msg, state)


async def _save_consultant(m, state):
    data = await state.get_data()
    await state.clear()
    async with AsyncSessionLocal() as db:
        await create_consultant(db, name=data["cons_name"], phone=data["cons_phone"],
                                telegram=data.get("cons_tg"), working_hours=data.get("cons_hours"))
    await m.answer("✅ مشاور اضافه شد.")


@router.callback_query(F.data.startswith("cons:del:"))
async def cons_delete(cb: CallbackQuery, db_user=None):
    if not _is_admin(db_user): return
    cid = int(cb.data.split(":")[2])
    async with AsyncSessionLocal() as db:
        await delete_consultant(db, cid)
    await cb.answer("🗑 مشاور حذف شد.", show_alert=True)
    await cb.message.delete()


# ── ارسال پیام همگانی ────────────────────────────────────
@router.message(F.text == "📢 ارسال پیام")
async def broadcast_start(msg: Message, state: FSMContext, db_user=None):
    if not _is_admin(db_user): return
    await state.set_state(AdminFSM.broadcast_text)
    await msg.answer("📢 متن پیام همگانی را بنویسید:")


@router.message(AdminFSM.broadcast_text, F.text)
async def broadcast_send(msg: Message, state: FSMContext):
    text = msg.text.strip()
    await state.clear()
    async with AsyncSessionLocal() as db:
        users = await list_users(db, limit=1000)
    sent = failed = 0
    for u in users:
        try:
            await msg.bot.send_message(u.telegram_id, text)
            sent += 1
        except Exception:
            failed += 1
    await msg.answer("📢 ارسال شد: " + str(sent) + " | ناموفق: " + str(failed))


# ── تنظیمات ──────────────────────────────────────────────
@router.message(F.text == "⚙️ تنظیمات")
async def settings_menu(msg: Message, db_user=None):
    if not _is_admin(db_user): return
    keys = [
        ("📞 تماس با ما",    "contact_info"),
        ("ℹ️ درباره ما",     "about_us"),
        ("📋 قوانین",        "rules"),
        ("🔔 گروه بازبینی",  "review_group_id"),
        ("💾 گروه بکاپ",     "backup_group_id"),
        ("⏱ بازه بکاپ (h)", "backup_interval_hours"),
    ]
    b = InlineKeyboardBuilder()
    for label, key in keys:
        b.button(text=label, callback_data="set:" + key)
    b.adjust(2)
    await msg.answer("⚙️ <b>تنظیمات</b>\nکدام مورد را ویرایش کنید:", reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("set:"))
async def setting_select(cb: CallbackQuery, state: FSMContext, db_user=None):
    if not _is_admin(db_user): return
    key = cb.data[4:]
    await state.update_data(setting_key=key)
    await state.set_state(AdminFSM.setting_value)
    async with AsyncSessionLocal() as db:
        current = await get_setting(db, key, "(خالی)")
    await cb.message.answer("✏️ مقدار جدید برای <b>" + key + "</b>:\n\nمقدار فعلی: " + current)
    await cb.answer()


@router.message(AdminFSM.setting_value, F.text)
async def setting_save(msg: Message, state: FSMContext):
    data = await state.get_data()
    key  = data["setting_key"]
    val  = msg.text.strip()
    await state.clear()
    async with AsyncSessionLocal() as db:
        await set_setting(db, key, val)
    await msg.answer("✅ تنظیم <b>" + key + "</b> ذخیره شد.")


# ── بکاپ دستی ────────────────────────────────────────────
@router.message(F.text == "💾 بکاپ")
async def manual_backup(msg: Message, db_user=None):
    if not _is_admin(db_user): return
    await msg.answer("⏳ در حال ساخت بکاپ...")
    try:
        from services.backup import send_backup
        await send_backup(msg.bot)
        await msg.answer("✅ بکاپ ساخته و ارسال شد.")
    except Exception as e:
        await msg.answer("❌ خطا در بکاپ: " + str(e))
        logger.error("manual backup error: %s", e)