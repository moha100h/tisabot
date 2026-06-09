from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup)
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🏠 ثبت آگهی"),    KeyboardButton(text="🔍 جستجوی ملک")],
        [KeyboardButton(text="📋 آگهی‌های من"), KeyboardButton(text="👥 مشاوران")],
        [KeyboardButton(text="📞 تماس با ما"),  KeyboardButton(text="ℹ️ درباره ما")],
    ], resize_keyboard=True)


def listing_type_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🏷 فروش",            callback_data="lt:sale")
    b.button(text="🏠 رهن و اجاره",     callback_data="lt:rent")
    b.button(text="🤝 مشارکت در ساخت",  callback_data="lt:partnership")
    b.button(text="🔙 بازگشت",          callback_data="lt:back")
    b.adjust(2, 1, 1)
    return b.as_markup()


def property_type_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🏢 آپارتمان", callback_data="pt:apartment")
    b.button(text="🏡 ویلا",     callback_data="pt:villa")
    b.button(text="🏪 تجاری",    callback_data="pt:commercial")
    b.button(text="🌿 زمین",     callback_data="pt:land")
    b.button(text="🏬 دفتر",     callback_data="pt:office")
    b.button(text="📦 سایر",     callback_data="pt:other")
    b.button(text="🔙 بازگشت",   callback_data="pt:back")
    b.adjust(2, 2, 2, 1)
    return b.as_markup()


def confirm_kb(prefix: str = "confirm") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ تأیید",   callback_data=f"{prefix}:yes")
    b.button(text="❌ انصراف", callback_data=f"{prefix}:no")
    b.adjust(2)
    return b.as_markup()


def skip_kb(cb: str = "skip") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⏭ رد کردن", callback_data=cb)
    b.button(text="🔙 بازگشت", callback_data="back")
    b.adjust(2)
    return b.as_markup()


def listing_card_kb(listing_id: int, owner_phone: str,
                    is_owner: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"📞 {owner_phone}", callback_data=f"call:{listing_id}")
    b.button(text="💬 مشاوره تلگرامی", callback_data=f"consult:{listing_id}")
    if is_owner:
        b.button(text="✏️ ویرایش", callback_data=f"edit_lst:{listing_id}")
        b.button(text="🗑 حذف",    callback_data=f"del_lst:{listing_id}")
    b.adjust(1)
    return b.as_markup()


def my_listing_status_kb(listing_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for label, val in [("✅ موجود","available"),("💰 فروخته شد","sold"),
                       ("🏠 اجاره رفت","rented"),("🔑 رهن رفت","mortgaged"),
                       ("⏸ غیرفعال","inactive")]:
        b.button(text=label, callback_data=f"setstatus:{listing_id}:{val}")
    b.button(text="🔙 بازگشت", callback_data="my_listings")
    b.adjust(2, 2, 1, 1)
    return b.as_markup()


def review_group_kb(listing_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ تأیید", callback_data=f"rev:approve:{listing_id}")
    b.button(text="❌ رد",    callback_data=f"rev:reject:{listing_id}")
    b.adjust(2)
    return b.as_markup()


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📋 مدیریت آگهی‌ها"), KeyboardButton(text="👥 مدیریت کاربران")],
        [KeyboardButton(text="👨‍💼 مشاوران"),        KeyboardButton(text="📢 ارسال پیام")],
        [KeyboardButton(text="⚙️ تنظیمات"),         KeyboardButton(text="💾 بکاپ")],
        [KeyboardButton(text="🔙 خروج از پنل ادمین")],
    ], resize_keyboard=True)


def contact_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📱 اشتراک‌گذاری شماره", request_contact=True)],
        [KeyboardButton(text="❌ انصراف")],
    ], resize_keyboard=True, one_time_keyboard=True)


def back_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔙 بازگشت", callback_data="back")
    return b.as_markup()
