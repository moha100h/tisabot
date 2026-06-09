from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.database import AsyncSessionLocal
from db.repository import (
    get_user, update_user, list_users, count_users, search_users,
    list_listings, get_listing, update_listing, delete_listing,
    list_consultants, create_consultant, delete_consultant,
    get_setting, set_setting
)
from db.models import UserRole, ListingStatus
from keyboards.main import admin_menu, main_menu, review_group_kb
import logging

router = Router()
logger = logging.getLogger("admin")

SETTINGS_KEYS = [
    ("📞 اطلاعات تماس",         "contact_info"),
    ("ℹ️ درباره ما",            "about_us"),
    ("📜 قوانین",               "rules"),
    ("🔍 گروه بازبینی",         "review_group_id"),
    ("💾 گروه بکاپ",            "backup_group_id"),
    ("⏱ فاصله بکاپ (ساعت)",    "backup_interval_hours"),
    ("📸 حداکثر تصویر آگهی",    "max_listing_images"),
    ("🏷 حداکثر آگهی هر کاربر", "max_listings_per_user"),
]


class AdminFSM(StatesGroup):
    broadcast_text   = State()
    setting_value    = State()
    rejection_reason = State()
    search_user      = State()
    add_admin_id     = State()


class ConsultantFSM(StatesGroup):
    name          = State()
    phone         = State()
    telegram      = State()
    working_hours = State()


def _is_admin(u):
    return u and u.role in (UserRole.ADMIN, UserRole.SUPER)

def _is_super(u):
    return u and u.role == UserRole.SUPER


@router.message(F.text == "/admin")
async def admin_panel(msg: Message, db_user=None):
    if not _is_admin(db_user):
        await msg.answer("⛔️ دسترسی ندارید.")
        return
    async with AsyncSessionLocal() as db:
        total   = await count_users(db)
        pending = await list_listings(db, status=ListingStatus.PENDING, limit=100)
    role_text = "سوپر ادمین" if _is_super(db_user) else "ادمین"
    await msg.answer(
        "👨‍💼 <b>پنل مدیریت</b>\n\n"
        "👥 کاربران: <b>" + str(total) + "</b>\n"
        "⏳ آگهی در انتظار: <b>" + str(len(pending)) + "</b>\n"
        "🔑 نقش: " + role_text,
        reply_markup=admin_menu()
    )


@router.message(F.text == "🔙 خروج از پنل ادمین")
async def exit_admin(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("✅ خارج شدید.", reply_markup=main_menu())


@router.message(F.text == "/cancel")
async def cancel_all(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("❌ لغو شد.")


# ── مدیریت آگهی‌ها ────────────────────────────────────────────
@router.message(F.text == "📋 مدیریت آگهی‌ها")
async def listings_menu(msg: Message, db_user=None):
    if not _is_admin(db_user): return
    b = InlineKeyboardBuilder()
    b.button(text="⏳ در انتظار", callback_data="adm_lst:pending")
    b.button(text="✅ تأیید شده", callback_data="adm_lst:approved")
    b.button(text="❌ رد شده",   callback_data="adm_lst:rejected")
    b.adjust(3)
    await msg.answer("📋 <b>مدیریت آگهی‌ها</b>", reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("adm_lst:"))
async def listing_filter(cb: CallbackQuery, db_user=None):
    if not _is_admin(db_user):
        await cb.answer("⛔️", show_alert=True); return
    val = cb.data.split(":")[1]
    smap = {"pending": ListingStatus.PENDING, "approved": ListingStatus.APPROVED, "rejected": ListingStatus.REJECTED}
    async with AsyncSessionLocal() as db:
        listings = await list_listings(db, status=smap[val], limit=10)
    if not listings:
        await cb.answer("📭 آگهی‌ای یافت نشد.", show_alert=True); return
    await cb.answer()
    for lst in listings:
        b = InlineKeyboardBuilder()
        if lst.status != ListingStatus.APPROVED:
            b.button(text="✅ تأیید", callback_data="rev:approve:" + str(lst.id))
        if lst.status != ListingStatus.REJECTED:
            b.button(text="❌ رد",    callback_data="rev:reject:"  + str(lst.id))
        b.button(text="🗑 حذف",      callback_data="adm_del:"     + str(lst.id))
        b.adjust(2, 1)
        owner = lst.owner
        text = (
            "🏷 <b>" + lst.code + "</b>\n"
            "📍 " + lst.province + " — " + lst.city + "\n"
            "👤 " + (owner.full_name if owner else "—") + "\n"
            "📊 " + lst.status.value
        )
        if lst.images:
            await cb.message.answer_photo(lst.images[0].file_id, caption=text, reply_markup=b.as_markup())
        else:
            await cb.message.answer(text, reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("adm_del:"))
async def admin_del_listing(cb: CallbackQuery, db_user=None):
    if not _is_admin(db_user):
        await cb.answer("⛔️", show_alert=True); return
    lid = int(cb.data.split(":")[1])
    async with AsyncSessionLocal() as db:
        await delete_listing(db, lid)
    await cb.answer("🗑 حذف شد.")
    await cb.message.delete()


@router.callback_query(F.data.startswith("rev:"))
async def review_action(cb: CallbackQuery, state: FSMContext, db_user=None):
    parts  = cb.data.split(":")
    action = parts[1]
    lid    = int(parts[2])
    if action == "reject":
        await state.set_state(AdminFSM.rejection_reason)
        await state.update_data(reject_lid=lid)
        await cb.message.answer("✏️ دلیل رد آگهی را وارد کنید:")
        await cb.answer(); return
    async with AsyncSessionLocal() as db:
        lst = await get_listing(db, lid)
        if not lst:
            await cb.answer("آگهی یافت نشد.", show_alert=True); return
        await update_listing(db, lid, status=ListingStatus.APPROVED)
        owner = lst.owner
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer("✅ آگهی <code>" + lst.code + "</code> تأیید شد.")
    if owner:
        try:
            await cb.bot.send_message(owner.telegram_id,
                "🎉 آگهی شما با کد <code>" + lst.code + "</code> تأیید و منتشر شد!")
        except Exception: pass
    await cb.answer("✅ تأیید شد.")


@router.message(AdminFSM.rejection_reason, F.text)
async def got_rejection(msg: Message, state: FSMContext):
    data   = await state.get_data()
    lid    = data["reject_lid"]
    reason = msg.text.strip()
    async with AsyncSessionLocal() as db:
        lst = await get_listing(db, lid)
        if lst:
            await update_listing(db, lid, status=ListingStatus.REJECTED, rejection_reason=reason)
            owner = lst.owner
        else:
            owner = None
    await state.clear()
    await msg.answer("❌ آگهی رد شد.\n📝 دلیل: " + reason)
    if owner and lst:
        try:
            await msg.bot.send_message(owner.telegram_id,
                "❌ آگهی <code>" + lst.code + "</code> رد شد.\n📝 دلیل: " + reason)
        except Exception: pass


# ── مدیریت کاربران ────────────────────────────────────────────
@router.message(F.text == "👥 مدیریت کاربران")
async def users_menu(msg: Message, db_user=None):
    if not _is_admin(db_user): return
    b = InlineKeyboardBuilder()
    b.button(text="📋 لیست",        callback_data="adm_usr:list")
    b.button(text="🔍 جستجو",       callback_data="adm_usr:search")
    b.button(text="👑 افزودن ادمین", callback_data="adm_usr:add_admin")
    b.adjust(2, 1)
    await msg.answer("👥 <b>مدیریت کاربران</b>", reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("adm_usr:"))
async def user_action(cb: CallbackQuery, state: FSMContext, db_user=None):
    if not _is_admin(db_user):
        await cb.answer("⛔️", show_alert=True); return
    val = cb.data.split(":")[1]
    if val == "list":
        async with AsyncSessionLocal() as db:
            users = await list_users(db, limit=10)
        await cb.answer()
        for u in users:
            b = InlineKeyboardBuilder()
            b.button(
                text="🚫 مسدود" if not u.is_blocked else "✅ رفع مسدودی",
                callback_data="adm_block:" + str(u.telegram_id) + ":" + str(int(not u.is_blocked))
            )
            await cb.message.answer(
                "👤 <b>" + u.full_name + "</b>\n📞 " + u.phone + "\n🆔 <code>" + str(u.telegram_id) + "</code>\n" +
                ("🚫 مسدود" if u.is_blocked else "✅ فعال"),
                reply_markup=b.as_markup()
            )
    elif val == "search":
        await state.set_state(AdminFSM.search_user)
        await cb.message.edit_text("🔍 نام یا شماره را وارد کنید:")
    elif val == "add_admin":
        await state.set_state(AdminFSM.add_admin_id)
        await cb.message.edit_text("👑 آیدی عددی تلگرام کاربر را وارد کنید:")


@router.message(AdminFSM.search_user, F.text)
async def search_user_h(msg: Message, state: FSMContext):
    async with AsyncSessionLocal() as db:
        users = await search_users(db, msg.text.strip())
    await state.clear()
    if not users:
        await msg.answer("📭 یافت نشد."); return
    for u in users:
        b = InlineKeyboardBuilder()
        b.button(
            text="🚫 مسدود" if not u.is_blocked else "✅ رفع مسدودی",
            callback_data="adm_block:" + str(u.telegram_id) + ":" + str(int(not u.is_blocked))
        )
        await msg.answer(
            "👤 <b>" + u.full_name + "</b>\n📞 " + u.phone + "\n🆔 <code>" + str(u.telegram_id) + "</code>",
            reply_markup=b.as_markup()
        )


@router.message(AdminFSM.add_admin_id, F.text)
async def add_admin_h(msg: Message, state: FSMContext, db_user=None):
    if not _is_super(db_user):
        await msg.answer("⛔️ فقط سوپر ادمین می‌تواند ادمین اضافه کند.")
        await state.clear(); return
    tid_str = msg.text.strip()
    if not tid_str.isdigit():
        await msg.answer("⚠️ آیدی باید عدد باشد."); return
    async with AsyncSessionLocal() as db:
        target = await get_user(db, int(tid_str))
        if not target:
            await msg.answer("❌ کاربر یافت نشد.")
            await state.clear(); return
        await update_user(db, int(tid_str), role=UserRole.ADMIN)
    await state.clear()
    await msg.answer("✅ <b>" + target.full_name + "</b> ادمین شد.")
    try:
        await msg.bot.send_message(int(tid_str), "👑 شما ادمین شدید.\n/admin برای ورود به پنل")
    except Exception: pass


@router.callback_query(F.data.startswith("adm_block:"))
async def block_user(cb: CallbackQuery, db_user=None):
    if not _is_admin(db_user):
        await cb.answer("⛔️", show_alert=True); return
    _, tid, blocked = cb.data.split(":")
    async with AsyncSessionLocal() as db:
        await update_user(db, int(tid), is_blocked=bool(int(blocked)))
    await cb.answer("✅ انجام شد.")
    await cb.message.delete()


# ── ارسال همگانی ──────────────────────────────────────────────
@router.message(F.text == "📢 ارسال پیام")
async def broadcast_start(msg: Message, state: FSMContext, db_user=None):
    if not _is_admin(db_user): return
    await state.set_state(AdminFSM.broadcast_text)
    await msg.answer("📢 متن یا فایل خود را ارسال کنید:\n<i>برای لغو: /cancel</i>")


@router.message(AdminFSM.broadcast_text)
async def do_broadcast(msg: Message, state: FSMContext):
    await state.clear()
    async with AsyncSessionLocal() as db:
        users = await list_users(db, limit=100000)
    sent = failed = 0
    for u in users:
        try:
            await msg.copy_to(u.telegram_id)
            sent += 1
        except Exception:
            failed += 1
    await msg.answer("📢 <b>ارسال تمام شد</b>\n✅ موفق: " + str(sent) + "\n❌ ناموفق: " + str(failed))


# ── تنظیمات ───────────────────────────────────────────────────
@router.message(F.text == "⚙️ تنظیمات")
async def admin_settings(msg: Message, db_user=None):
    if not _is_admin(db_user): return
    b = InlineKeyboardBuilder()
    for label, key in SETTINGS_KEYS:
        b.button(text=label, callback_data="adm_set:" + key)
    b.adjust(2)
    await msg.answer("⚙️ <b>تنظیمات ربات</b>\nکدام مورد را ویرایش کنید؟", reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("adm_set:"))
async def set_key(cb: CallbackQuery, state: FSMContext):
    key = cb.data.split(":")[1]
    await state.set_state(AdminFSM.setting_value)
    await state.update_data(setting_key=key)
    async with AsyncSessionLocal() as db:
        current = await get_setting(db, key, "—")
    label = next((l for l, k in SETTINGS_KEYS if k == key), key)
    await cb.message.edit_text(
        "⚙️ <b>" + label + "</b>\n\n"
        "مقدار فعلی: <code>" + current + "</code>\n\n"
        "مقدار جدید را وارد کنید:"
    )


@router.message(AdminFSM.setting_value, F.text)
async def save_setting(msg: Message, state: FSMContext):
    data = await state.get_data()
    key  = data["setting_key"]
    val  = msg.text.strip()
    async with AsyncSessionLocal() as db:
        await set_setting(db, key, val)
    await state.clear()
    label = next((l for l, k in SETTINGS_KEYS if k == key), key)
    await msg.answer("✅ <b>" + label + "</b> ذخیره شد: <code>" + val + "</code>")
    if key == "backup_interval_hours" and val.isdigit():
        try:
            from services.backup import stop_scheduler, start_scheduler
            stop_scheduler()
            start_scheduler(msg.bot, interval_hours=int(val))
        except Exception: pass


# ── مشاوران ───────────────────────────────────────────────────
@router.message(F.text == "👨‍💼 مشاوران")
async def admin_consultants(msg: Message, db_user=None):
    if not _is_admin(db_user): return
    async with AsyncSessionLocal() as db:
        consultants = await list_consultants(db)
    b = InlineKeyboardBuilder()
    b.button(text="➕ افزودن", callback_data="adm_con:add")
    await msg.answer("👨‍💼 <b>مشاوران (" + str(len(consultants)) + " نفر)</b>", reply_markup=b.as_markup())
    for c in consultants:
        b2 = InlineKeyboardBuilder()
        b2.button(text="🗑 حذف", callback_data="adm_con:del:" + str(c.id))
        text = "👤 <b>" + c.name + "</b>\n📞 " + c.phone
        if c.telegram:      text += "\n💬 @" + c.telegram
        if c.working_hours: text += "\n🕐 " + c.working_hours
        await msg.answer(text, reply_markup=b2.as_markup())


@router.callback_query(F.data == "adm_con:add")
async def add_con_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(ConsultantFSM.name)
    await cb.message.answer("👤 نام مشاور:")
    await cb.answer()


@router.message(ConsultantFSM.name, F.text)
async def con_name(msg: Message, state: FSMContext):
    await state.update_data(name=msg.text.strip())
    await state.set_state(ConsultantFSM.phone)
    await msg.answer("📞 شماره تماس:")


@router.message(ConsultantFSM.phone, F.text)
async def con_phone(msg: Message, state: FSMContext):
    await state.update_data(phone=msg.text.strip())
    await state.set_state(ConsultantFSM.telegram)
    b = InlineKeyboardBuilder()
    b.button(text="⏭ رد کردن", callback_data="skip:con_tg")
    await msg.answer("💬 یوزرنیم تلگرام (بدون @):", reply_markup=b.as_markup())


@router.callback_query(F.data == "skip:con_tg")
async def skip_con_tg(cb: CallbackQuery, state: FSMContext):
    await state.update_data(telegram=None)
    await state.set_state(ConsultantFSM.working_hours)
    b = InlineKeyboardBuilder()
    b.button(text="⏭ رد کردن", callback_data="skip:con_wh")
    await cb.message.answer("🕐 ساعات کاری:", reply_markup=b.as_markup())


@router.message(ConsultantFSM.telegram, F.text)
async def con_tg(msg: Message, state: FSMContext):
    await state.update_data(telegram=msg.text.strip().lstrip("@"))
    await state.set_state(ConsultantFSM.working_hours)
    b = InlineKeyboardBuilder()
    b.button(text="⏭ رد کردن", callback_data="skip:con_wh")
    await msg.answer("🕐 ساعات کاری:", reply_markup=b.as_markup())


@router.callback_query(F.data == "skip:con_wh")
async def skip_con_wh(cb: CallbackQuery, state: FSMContext):
    await state.update_data(working_hours=None)
    await _save_con(cb.message, state)


@router.message(ConsultantFSM.working_hours, F.text)
async def con_wh(msg: Message, state: FSMContext):
    await state.update_data(working_hours=msg.text.strip())
    await _save_con(msg, state)


async def _save_con(m, state):
    data = await state.get_data()
    await state.clear()
    async with AsyncSessionLocal() as db:
        c = await create_consultant(db, **{k: v for k, v in data.items() if v is not None})
    await m.answer("✅ مشاور <b>" + c.name + "</b> اضافه شد.")


@router.callback_query(F.data.startswith("adm_con:del:"))
async def del_con(cb: CallbackQuery, db_user=None):
    if not _is_admin(db_user):
        await cb.answer("⛔️", show_alert=True); return
    cid = int(cb.data.split(":")[2])
    async with AsyncSessionLocal() as db:
        await delete_consultant(db, cid)
    await cb.answer("🗑 حذف شد.")
    await cb.message.delete()
