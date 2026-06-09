from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.database import AsyncSessionLocal
from db.repository import (
    get_user, update_user, list_users, count_users,
    list_listings, get_listing, update_listing, delete_listing,
    list_consultants, create_consultant, delete_consultant,
    get_setting, set_setting
)
from db.models import UserRole, ListingStatus
from keyboards.main import admin_menu, main_menu
import logging

router = Router()
logger = logging.getLogger("admin")


def _is_admin(db_user) -> bool:
    return db_user and db_user.role in (UserRole.ADMIN, UserRole.SUPER)


def _is_super(db_user) -> bool:
    return db_user and db_user.role == UserRole.SUPER


# ── FSM ───────────────────────────────────────────────────────
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


# ── ورود به پنل ───────────────────────────────────────────────
@router.message(F.text == "/admin")
async def admin_panel(msg: Message, db_user=None):
    if not _is_admin(db_user):
        await msg.answer("⛔️ دسترسی ندارید.")
        return
    async with AsyncSessionLocal() as db:
        total = await count_users(db)
        pending = await list_listings(db, status=ListingStatus.PENDING, limit=100)
    await msg.answer(
        f"👨‍💼 <b>پنل مدیریت</b>

"
        f"👥 کاربران: <b>{total}</b>
"
        f"⏳ آگهی در انتظار تأیید: <b>{len(pending)}</b>
"
        f"🔑 نقش: {'سوپر ادمین' if _is_super(db_user) else 'ادمین'}",
        reply_markup=admin_menu()
    )


@router.message(F.text == "🔙 خروج از پنل ادمین")
async def exit_admin(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("✅ از پنل ادمین خارج شدید.", reply_markup=main_menu())


# ── مدیریت آگهی‌ها ────────────────────────────────────────────
@router.message(F.text == "📋 مدیریت آگهی‌ها")
async def admin_listings_menu(msg: Message, db_user=None):
    if not _is_admin(db_user): return
    b = InlineKeyboardBuilder()
    b.button(text="⏳ در انتظار تأیید", callback_data="adm_lst:pending")
    b.button(text="✅ تأیید شده",       callback_data="adm_lst:approved")
    b.button(text="❌ رد شده",          callback_data="adm_lst:rejected")
    b.adjust(2, 1)
    await msg.answer("📋 <b>مدیریت آگهی‌ها</b>", reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("adm_lst:"))
async def admin_listing_filter(cb: CallbackQuery, db_user=None):
    if not _is_admin(db_user):
        await cb.answer("⛔️", show_alert=True); return
    val = cb.data.split(":")[1]
    status_map = {
        "pending":  ListingStatus.PENDING,
        "approved": ListingStatus.APPROVED,
        "rejected": ListingStatus.REJECTED,
    }
    async with AsyncSessionLocal() as db:
        listings = await list_listings(db, status=status_map[val], limit=10)
    if not listings:
        await cb.answer("📭 آگهی‌ای یافت نشد.", show_alert=True); return
    await cb.answer()
    for lst in listings:
        b = InlineKeyboardBuilder()
        if lst.status != ListingStatus.APPROVED:
            b.button(text="✅ تأیید", callback_data=f"rev:approve:{lst.id}")
        if lst.status != ListingStatus.REJECTED:
            b.button(text="❌ رد",    callback_data=f"rev:reject:{lst.id}")
        b.button(text="🗑 حذف",      callback_data=f"adm_del:{lst.id}")
        b.adjust(2, 1)
        owner = lst.owner
        text = (
            f"🏷 <b>{lst.code}</b>
"
            f"📍 {lst.province} — {lst.city}
"
            f"👤 {owner.full_name if owner else '—'} | 📞 {owner.phone if owner else '—'}
"
            f"📊 {lst.status.value}"
        )
        if lst.images:
            await cb.message.answer_photo(lst.images[0].file_id, caption=text, reply_markup=b.as_markup())
        else:
            await cb.message.answer(text, reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("adm_del:"))
async def admin_delete_listing(cb: CallbackQuery, db_user=None):
    if not _is_admin(db_user):
        await cb.answer("⛔️", show_alert=True); return
    lid = int(cb.data.split(":")[1])
    async with AsyncSessionLocal() as db:
        await delete_listing(db, lid)
    await cb.answer("🗑 آگهی حذف شد.")
    await cb.message.delete()


# ── بازبینی گروهی ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("rev:"))
async def review_action(cb: CallbackQuery, state: FSMContext, db_user=None):
    parts  = cb.data.split(":")
    action = parts[1]
    lid    = int(parts[2])

    if action == "reject":
        await state.set_state(AdminFSM.rejection_reason)
        await state.update_data(reject_lid=lid)
        await cb.message.answer("✏️ دلیل رد آگهی را وارد کنید:")
        await cb.answer()
        return

    async with AsyncSessionLocal() as db:
        lst = await get_listing(db, lid)
        if not lst:
            await cb.answer("آگهی یافت نشد.", show_alert=True); return
        await update_listing(db, lid, status=ListingStatus.APPROVED)
        owner = lst.owner

    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(f"✅ آگهی <code>{lst.code}</code> تأیید شد.")
    if owner:
        try:
            await cb.bot.send_message(
                owner.telegram_id,
                f"🎉 آگهی شما با کد <code>{lst.code}</code> تأیید و منتشر شد!"
            )
        except Exception: pass
    await cb.answer("✅ تأیید شد.")


@router.message(AdminFSM.rejection_reason, F.text)
async def got_rejection_reason(msg: Message, state: FSMContext):
    data   = await state.get_data()
    lid    = data["reject_lid"]
    reason = msg.text.strip()
    async with AsyncSessionLocal() as db:
        lst = await get_listing(db, lid)
        if lst:
            await update_listing(db, lid,
                status=ListingStatus.REJECTED, rejection_reason=reason)
            owner = lst.owner
        else:
            owner = None
    await state.clear()
    await msg.answer(f"❌ آگهی رد شد.
📝 دلیل: {reason}")
    if owner:
        try:
            await msg.bot.send_message(
                owner.telegram_id,
                f"❌ آگهی شما با کد <code>{lst.code}</code> رد شد.
📝 دلیل: {reason}"
            )
        except Exception: pass


# ── مدیریت کاربران ────────────────────────────────────────────
@router.message(F.text == "👥 مدیریت کاربران")
async def admin_users_menu(msg: Message, db_user=None):
    if not _is_admin(db_user): return
    b = InlineKeyboardBuilder()
    b.button(text="📋 لیست کاربران",  callback_data="adm_usr:list")
    b.button(text="🔍 جستجو",         callback_data="adm_usr:search")
    b.button(text="👑 افزودن ادمین",  callback_data="adm_usr:add_admin")
    b.adjust(2, 1)
    await msg.answer("👥 <b>مدیریت کاربران</b>", reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("adm_usr:"))
async def admin_user_action(cb: CallbackQuery, state: FSMContext, db_user=None):
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
                callback_data=f"adm_block:{u.telegram_id}:{int(not u.is_blocked)}"
            )
            b.button(text="📋 آگهی‌ها", callback_data=f"adm_ulst:{u.telegram_id}")
            b.adjust(2)
            await cb.message.answer(
                f"👤 <b>{u.full_name}</b>
"
                f"📞 {u.phone}
"
                f"🆔 <code>{u.telegram_id}</code>
"
                f"📅 {u.created_at.strftime('%Y/%m/%d')}
"
                f"{'🚫 مسدود' if u.is_blocked else '✅ فعال'}",
                reply_markup=b.as_markup()
            )

    elif val == "search":
        await state.set_state(AdminFSM.search_user)
        await cb.message.edit_text("🔍 نام، شماره یا یوزرنیم را وارد کنید:")

    elif val == "add_admin":
        await state.set_state(AdminFSM.add_admin_id)
        await cb.message.edit_text(
            "👑 آیدی عددی تلگرام کاربر را وارد کنید:
"
            "<i>(کاربر باید قبلاً ثبت‌نام کرده باشد)</i>"
        )


@router.message(AdminFSM.search_user, F.text)
async def search_user_handler(msg: Message, state: FSMContext):
    from db.repository import search_users
    async with AsyncSessionLocal() as db:
        users = await search_users(db, msg.text.strip())
    await state.clear()
    if not users:
        await msg.answer("📭 کاربری یافت نشد.")
        return
    for u in users:
        b = InlineKeyboardBuilder()
        b.button(
            text="🚫 مسدود" if not u.is_blocked else "✅ رفع مسدودی",
            callback_data=f"adm_block:{u.telegram_id}:{int(not u.is_blocked)}"
        )
        b.adjust(1)
        await msg.answer(
            f"👤 <b>{u.full_name}</b>
📞 {u.phone}
🆔 <code>{u.telegram_id}</code>",
            reply_markup=b.as_markup()
        )


@router.message(AdminFSM.add_admin_id, F.text)
async def add_admin_handler(msg: Message, state: FSMContext, db_user=None):
    if not _is_super(db_user):
        await msg.answer("⛔️ فقط سوپر ادمین می‌تواند ادمین اضافه کند.")
        await state.clear(); return
    tid_str = msg.text.strip()
    if not tid_str.isdigit():
        await msg.answer("⚠️ آیدی باید عدد باشد."); return
    async with AsyncSessionLocal() as db:
        target = await get_user(db, int(tid_str))
        if not target:
            await msg.answer("❌ کاربر یافت نشد. باید ابتدا ثبت‌نام کرده باشد.")
            await state.clear(); return
        await update_user(db, int(tid_str), role=UserRole.ADMIN)
    await state.clear()
    await msg.answer(f"✅ <b>{target.full_name}</b> به عنوان ادمین تعیین شد.")
    try:
        await msg.bot.send_message(int(tid_str),
            "👑 شما به عنوان ادمین ربات تعیین شدید.
/admin برای ورود به پنل مدیریت")
    except Exception: pass


@router.callback_query(F.data.startswith("adm_block:"))
async def admin_block_user(cb: CallbackQuery, db_user=None):
    if not _is_admin(db_user):
        await cb.answer("⛔️", show_alert=True); return
    _, tid, blocked = cb.data.split(":")
    async with AsyncSessionLocal() as db:
        await update_user(db, int(tid), is_blocked=bool(int(blocked)))
    status = "مسدود" if int(blocked) else "رفع مسدودی"
    await cb.answer(f"✅ {status} شد.")
    await cb.message.delete()


@router.callback_query(F.data.startswith("adm_ulst:"))
async def admin_user_listings(cb: CallbackQuery, db_user=None):
    if not _is_admin(db_user):
        await cb.answer("⛔️", show_alert=True); return
    tid = int(cb.data.split(":")[1])
    async with AsyncSessionLocal() as db:
        listings = await list_listings(db, owner_id=tid, limit=10)
    await cb.answer()
    if not listings:
        await cb.message.answer("📭 این کاربر آگهی ندارد."); return
    for lst in listings:
        b = InlineKeyboardBuilder()
        b.button(text="🗑 حذف", callback_data=f"adm_del:{lst.id}")
        await cb.message.answer(
            f"🏷 {lst.code} | {lst.province} — {lst.city} | {lst.status.value}",
            reply_markup=b.as_markup()
        )


# ── ارسال پیام همگانی ─────────────────────────────────────────
@router.message(F.text == "📢 ارسال پیام")
async def admin_broadcast_start(msg: Message, state: FSMContext, db_user=None):
    if not _is_admin(db_user): return
    await state.set_state(AdminFSM.broadcast_text)
    await msg.answer(
        "📢 <b>ارسال پیام همگانی</b>

"
        "متن، عکس یا فایل خود را ارسال کنید:
"
        "<i>برای لغو: /cancel</i>"
    )


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
    await msg.answer(
        f"📢 <b>ارسال تمام شد</b>

"
        f"✅ موفق: {sent}
❌ ناموفق: {failed}"
    )


# ── تنظیمات (همه از DB) ───────────────────────────────────────
SETTINGS_KEYS = [
    ("📞 اطلاعات تماس",       "contact_info"),
    ("ℹ️ درباره ما",          "about_us"),
    ("📜 قوانین و مقررات",    "rules"),
    ("❓ راهنمای استفاده",    "help_text"),
    ("🔍 گروه بازبینی آگهی",  "review_group_id"),
    ("💾 گروه بکاپ",          "backup_group_id"),
    ("⏱ فاصله بکاپ (ساعت)",  "backup_interval_hours"),
    ("📸 حداکثر تصویر آگهی",  "max_listing_images"),
    ("📏 حداکثر حجم تصویر MB","max_image_size_mb"),
    ("🏷 حداکثر آگهی هر کاربر","max_listings_per_user"),
]


@router.message(F.text == "⚙️ تنظیمات")
async def admin_settings(msg: Message, db_user=None):
    if not _is_admin(db_user): return
    b = InlineKeyboardBuilder()
    for label, key in SETTINGS_KEYS:
        b.button(text=label, callback_data=f"adm_set:{key}")
    b.adjust(2)
    await msg.answer("⚙️ <b>تنظیمات ربات</b>
کدام مورد را ویرایش کنید؟",
                     reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("adm_set:"))
async def admin_set_key(cb: CallbackQuery, state: FSMContext):
    key = cb.data.split(":")[1]
    await state.set_state(AdminFSM.setting_value)
    await state.update_data(setting_key=key)
    async with AsyncSessionLocal() as db:
        current = await get_setting(db, key, "—")
    label = next((l for l, k in SETTINGS_KEYS if k == key), key)
    hints = {
        "review_group_id":       "آیدی عددی گروه (مثال: -1001234567890)",
        "backup_group_id":       "آیدی عددی گروه (مثال: -1001234567890)",
        "backup_interval_hours": "عدد ساعت (مثال: 6)",
        "max_listing_images":    "عدد (مثال: 3)",
        "max_image_size_mb":     "عدد مگابایت (مثال: 5)",
        "max_listings_per_user": "عدد (مثال: 10)",
    }
    hint = hints.get(key, "")
    await cb.message.edit_text(
        f"⚙️ <b>{label}</b>

"
        f"مقدار فعلی: <code>{current}</code>
"
        + (f"💡 {hint}
" if hint else "") +
        "
مقدار جدید را وارد کنید:"
    )


@router.message(AdminFSM.setting_value, F.text)
async def admin_save_setting(msg: Message, state: FSMContext):
    data = await state.get_data()
    key  = data["setting_key"]
    val  = msg.text.strip()
    async with AsyncSessionLocal() as db:
        await set_setting(db, key, val)
    await state.clear()
    label = next((l for l, k in SETTINGS_KEYS if k == key), key)
    await msg.answer(f"✅ <b>{label}</b> ذخیره شد: <code>{val}</code>")

    # اگر فاصله بکاپ تغییر کرد، scheduler رو ری‌استارت کن
    if key == "backup_interval_hours" and val.isdigit():
        try:
            from services.backup_service import stop_scheduler, start_scheduler
            stop_scheduler()
            start_scheduler(msg.bot, interval_hours=int(val))
            await msg.answer(f"🔄 بکاپ خودکار هر {val} ساعت تنظیم شد.")
        except Exception as e:
            logger.warning(f"Could not restart scheduler: {e}")


# ── مدیریت مشاوران ────────────────────────────────────────────
@router.message(F.text == "👨‍💼 مشاوران")
async def admin_consultants(msg: Message, db_user=None):
    if not _is_admin(db_user): return
    async with AsyncSessionLocal() as db:
        consultants = await list_consultants(db)
    b = InlineKeyboardBuilder()
    b.button(text="➕ افزودن مشاور", callback_data="adm_con:add")
    b.adjust(1)
    await msg.answer(f"👨‍💼 <b>مشاوران ({len(consultants)} نفر)</b>",
                     reply_markup=b.as_markup())
    for c in consultants:
        b2 = InlineKeyboardBuilder()
        b2.button(text="🗑 حذف", callback_data=f"adm_con:del:{c.id}")
        await msg.answer(
            f"👤 <b>{c.name}</b>
📞 {c.phone}"
            + (f"
💬 @{c.telegram}" if c.telegram else "")
            + (f"
🕐 {c.working_hours}" if c.working_hours else ""),
            reply_markup=b2.as_markup()
        )


@router.callback_query(F.data == "adm_con:add")
async def add_consultant_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(ConsultantFSM.name)
    await cb.message.answer("👤 نام مشاور را وارد کنید:")
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
    b.button(text="⏭ رد کردن", callback_data="skip_con_tg")
    await msg.answer("💬 یوزرنیم تلگرام (بدون @):", reply_markup=b.as_markup())


@router.callback_query(ConsultantFSM.telegram, F.data == "skip_con_tg")
async def skip_con_tg(cb: CallbackQuery, state: FSMContext):
    await state.update_data(telegram=None)
    await state.set_state(ConsultantFSM.working_hours)
    b = InlineKeyboardBuilder()
    b.button(text="⏭ رد کردن", callback_data="skip_con_wh")
    await cb.message.answer("🕐 ساعات کاری:", reply_markup=b.as_markup())


@router.message(ConsultantFSM.telegram, F.text)
async def con_telegram(msg: Message, state: FSMContext):
    await state.update_data(telegram=msg.text.strip().lstrip("@"))
    await state.set_state(ConsultantFSM.working_hours)
    b = InlineKeyboardBuilder()
    b.button(text="⏭ رد کردن", callback_data="skip_con_wh")
    await msg.answer("🕐 ساعات کاری:", reply_markup=b.as_markup())


@router.callback_query(ConsultantFSM.working_hours, F.data == "skip_con_wh")
async def skip_con_wh(cb: CallbackQuery, state: FSMContext):
    await state.update_data(working_hours=None)
    await _save_consultant(cb.message, state)


@router.message(ConsultantFSM.working_hours, F.text)
async def con_wh(msg: Message, state: FSMContext):
    await state.update_data(working_hours=msg.text.strip())
    await _save_consultant(msg, state)


async def _save_consultant(m, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    async with AsyncSessionLocal() as db:
        c = await create_consultant(db, **{k: v for k, v in data.items() if v is not None})
    await m.answer(f"✅ مشاور <b>{c.name}</b> اضافه شد.")


@router.callback_query(F.data.startswith("adm_con:del:"))
async def del_consultant(cb: CallbackQuery, db_user=None):
    if not _is_admin(db_user):
        await cb.answer("⛔️", show_alert=True); return
    cid = int(cb.data.split(":")[2])
    async with AsyncSessionLocal() as db:
        await delete_consultant(db, cid)
    await cb.answer("🗑 مشاور حذف شد.")
    await cb.message.delete()


# ── /cancel ───────────────────────────────────────────────────
@router.message(F.text == "/cancel")
async def cancel_handler(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("❌ عملیات لغو شد.", reply_markup=main_menu())
