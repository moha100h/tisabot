from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, PhotoSize
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.database import AsyncSessionLocal
from db.repository import create_listing, add_listing_image, get_setting, update_listing
from db.models import ListingType, PropertyType
from keyboards.main import listing_type_kb, property_type_kb, confirm_kb, review_group_kb
from utils.helpers import to_int, norm_phone, fmt
import logging

router = Router()
logger = logging.getLogger("listing")

MAX_IMAGES   = 5
MAX_IMG_SIZE = 5 * 1024 * 1024

TYPE_MAP = {"sale": "فروش", "rent": "رهن/اجاره", "partnership": "مشارکت"}
PROP_MAP = {"apartment": "آپارتمان", "villa": "ویلا", "commercial": "تجاری",
            "land": "زمین", "office": "دفتر", "other": "سایر"}


class ListingFSM(StatesGroup):
    lst_type      = State()
    prop_type     = State()
    province      = State()
    city          = State()
    district      = State()
    address       = State()
    contact_phone = State()
    area          = State()
    bedrooms      = State()
    price         = State()
    mortgage      = State()
    rent_amt      = State()
    facilities    = State()
    description   = State()
    images        = State()
    confirm       = State()


def _skip_kb(cb: str) -> object:
    b = InlineKeyboardBuilder()
    b.button(text="⏭ رد کردن", callback_data=cb)
    return b.as_markup()


@router.message(F.text == "🏠 ثبت آگهی")
async def start_listing(msg: Message, state: FSMContext, db_user=None):
    if not db_user:
        await msg.answer("⚠️ ابتدا ثبت‌نام کنید. /start")
        return
    await state.clear()
    await state.set_state(ListingFSM.lst_type)
    await msg.answer("📋 <b>ثبت آگهی جدید</b>\nنوع معامله را انتخاب کنید:",
                     reply_markup=listing_type_kb())


@router.callback_query(ListingFSM.lst_type, F.data.startswith("lt:"))
async def got_type(cb: CallbackQuery, state: FSMContext):
    val = cb.data.split(":")[1]
    if val == "back":
        await state.clear()
        await cb.message.delete()
        return
    await state.update_data(listing_type=val)
    await state.set_state(ListingFSM.prop_type)
    await cb.message.edit_text("🏠 نوع ملک را انتخاب کنید:", reply_markup=property_type_kb())


@router.callback_query(ListingFSM.prop_type, F.data.startswith("pt:"))
async def got_prop(cb: CallbackQuery, state: FSMContext):
    val = cb.data.split(":")[1]
    if val == "back":
        await state.set_state(ListingFSM.lst_type)
        await cb.message.edit_text("نوع معامله را انتخاب کنید:", reply_markup=listing_type_kb())
        return
    await state.update_data(property_type=val)
    await state.set_state(ListingFSM.province)
    await cb.message.edit_text("📍 <b>استان</b> ملک را وارد کنید:")


@router.message(ListingFSM.province, F.text)
async def got_province(msg: Message, state: FSMContext):
    await state.update_data(province=msg.text.strip())
    await state.set_state(ListingFSM.city)
    await msg.answer("🏙 <b>شهر</b> را وارد کنید:")


@router.message(ListingFSM.city, F.text)
async def got_city(msg: Message, state: FSMContext):
    await state.update_data(city=msg.text.strip())
    await state.set_state(ListingFSM.district)
    await msg.answer("🏘 <b>محله</b> را وارد کنید:", reply_markup=_skip_kb("skip:district"))


@router.callback_query(ListingFSM.district, F.data == "skip:district")
async def skip_district(cb: CallbackQuery, state: FSMContext):
    await state.update_data(district=None)
    await state.set_state(ListingFSM.address)
    await cb.message.edit_text("📍 <b>آدرس کامل</b> ملک را وارد کنید:")


@router.message(ListingFSM.district, F.text)
async def got_district(msg: Message, state: FSMContext):
    await state.update_data(district=msg.text.strip())
    await state.set_state(ListingFSM.address)
    await msg.answer("📍 <b>آدرس کامل</b> ملک را وارد کنید:")


@router.message(ListingFSM.address, F.text)
async def got_address(msg: Message, state: FSMContext):
    await state.update_data(address=msg.text.strip())
    await state.set_state(ListingFSM.contact_phone)
    await msg.answer("📞 <b>شماره تماس جهت بازدید</b> را وارد کنید:\n(مثال: 09121234567)")


@router.message(ListingFSM.contact_phone, F.text)
async def got_contact_phone(msg: Message, state: FSMContext):
    phone = norm_phone(msg.text.strip())
    if not (phone.startswith("09") and len(phone) == 11 and phone.isdigit()):
        await msg.answer("⚠️ شماره معتبر نیست. مثال: 09121234567")
        return
    await state.update_data(contact_phone=phone)
    await state.set_state(ListingFSM.area)
    await msg.answer("📐 <b>متراژ</b> (متر مربع) را وارد کنید:",
                     reply_markup=_skip_kb("skip:area"))


@router.callback_query(ListingFSM.area, F.data == "skip:area")
async def skip_area(cb: CallbackQuery, state: FSMContext):
    await state.update_data(area=None)
    await state.set_state(ListingFSM.bedrooms)
    await cb.message.edit_text("🛏 <b>تعداد اتاق خواب</b> را وارد کنید:",
                               reply_markup=_skip_kb("skip:bedrooms"))


@router.message(ListingFSM.area, F.text)
async def got_area(msg: Message, state: FSMContext):
    val = to_int(msg.text)
    if val is None:
        await msg.answer("⚠️ عدد وارد کنید.")
        return
    await state.update_data(area=val)
    await state.set_state(ListingFSM.bedrooms)
    await msg.answer("🛏 <b>تعداد اتاق خواب</b> را وارد کنید:",
                     reply_markup=_skip_kb("skip:bedrooms"))


@router.callback_query(ListingFSM.bedrooms, F.data == "skip:bedrooms")
async def skip_bedrooms(cb: CallbackQuery, state: FSMContext):
    await state.update_data(bedrooms=None)
    await _price_step(cb.message, state)


@router.message(ListingFSM.bedrooms, F.text)
async def got_bedrooms(msg: Message, state: FSMContext):
    val = to_int(msg.text)
    if val is None:
        await msg.answer("⚠️ عدد وارد کنید.")
        return
    await state.update_data(bedrooms=val)
    await _price_step(msg, state)


async def _price_step(m, state):
    data = await state.get_data()
    if data.get("listing_type") == "sale":
        await state.set_state(ListingFSM.price)
        await m.answer("💵 <b>قیمت کل</b> (تومان) را وارد کنید:")
    else:
        await state.set_state(ListingFSM.mortgage)
        await m.answer("🔑 <b>مبلغ رهن</b> (تومان) را وارد کنید:",
                       reply_markup=_skip_kb("skip:mortgage"))


@router.message(ListingFSM.price, F.text)
async def got_price(msg: Message, state: FSMContext):
    val = to_int(msg.text)
    if val is None:
        await msg.answer("⚠️ عدد وارد کنید.")
        return
    await state.update_data(price=val)
    await _facilities_step(msg, state)


@router.callback_query(ListingFSM.mortgage, F.data == "skip:mortgage")
async def skip_mortgage(cb: CallbackQuery, state: FSMContext):
    await state.update_data(mortgage=None)
    await state.set_state(ListingFSM.rent_amt)
    await cb.message.edit_text("🏠 <b>اجاره ماهانه</b> (تومان) را وارد کنید:",
                               reply_markup=_skip_kb("skip:rent"))


@router.message(ListingFSM.mortgage, F.text)
async def got_mortgage(msg: Message, state: FSMContext):
    val = to_int(msg.text)
    if val is None:
        await msg.answer("⚠️ عدد وارد کنید.")
        return
    await state.update_data(mortgage=val)
    await state.set_state(ListingFSM.rent_amt)
    await msg.answer("🏠 <b>اجاره ماهانه</b> (تومان) را وارد کنید:",
                     reply_markup=_skip_kb("skip:rent"))


@router.callback_query(ListingFSM.rent_amt, F.data == "skip:rent")
async def skip_rent(cb: CallbackQuery, state: FSMContext):
    await state.update_data(rent=None)
    await _facilities_step(cb.message, state)


@router.message(ListingFSM.rent_amt, F.text)
async def got_rent(msg: Message, state: FSMContext):
    val = to_int(msg.text)
    if val is None:
        await msg.answer("⚠️ عدد وارد کنید.")
        return
    await state.update_data(rent=val)
    await _facilities_step(msg, state)


async def _facilities_step(m, state):
    await state.set_state(ListingFSM.facilities)
    await m.answer("🏊 <b>امکانات</b> را وارد کنید:\n(مثال: آسانسور، پارکینگ، انباری)",
                   reply_markup=_skip_kb("skip:fac"))


@router.callback_query(ListingFSM.facilities, F.data == "skip:fac")
async def skip_fac(cb: CallbackQuery, state: FSMContext):
    await state.update_data(facilities=None)
    await _desc_step(cb.message, state)


@router.message(ListingFSM.facilities, F.text)
async def got_fac(msg: Message, state: FSMContext):
    await state.update_data(facilities=msg.text.strip())
    await _desc_step(msg, state)


async def _desc_step(m, state):
    await state.set_state(ListingFSM.description)
    await m.answer("📝 <b>توضیحات تکمیلی</b> را وارد کنید:",
                   reply_markup=_skip_kb("skip:desc"))


@router.callback_query(ListingFSM.description, F.data == "skip:desc")
async def skip_desc(cb: CallbackQuery, state: FSMContext):
    await state.update_data(description=None)
    await _ask_images(cb.message, state)


@router.message(ListingFSM.description, F.text)
async def got_desc(msg: Message, state: FSMContext):
    await state.update_data(description=msg.text.strip())
    await _ask_images(msg, state)


async def _ask_images(m, state):
    await state.set_state(ListingFSM.images)
    await state.update_data(images=[])
    await m.answer(
        "📸 <b>تصاویر ملک</b>\n"
        "حداکثر " + str(MAX_IMAGES) + " تصویر — هر کدام حداکثر ۵ مگابایت",
        reply_markup=_skip_kb("skip:images")
    )


@router.message(ListingFSM.images, F.photo)
async def got_image(msg: Message, state: FSMContext):
    data   = await state.get_data()
    images = data.get("images", [])
    photo: PhotoSize = msg.photo[-1]
    if photo.file_size and photo.file_size > MAX_IMG_SIZE:
        await msg.answer("⚠️ حجم تصویر بیشتر از ۵ مگابایت است.")
        return
    images.append(photo.file_id)
    await state.update_data(images=images)
    remaining = MAX_IMAGES - len(images)
    if remaining > 0:
        b = InlineKeyboardBuilder()
        b.button(text="✅ همین کافیه", callback_data="skip:images")
        await msg.answer(
            "✅ تصویر " + str(len(images)) + " دریافت شد."
            + (" " + str(remaining) + " تصویر دیگر می‌توانید ارسال کنید." if remaining else ""),
            reply_markup=b.as_markup()
        )
    else:
        await _show_confirm(msg, state)


@router.callback_query(ListingFSM.images, F.data == "skip:images")
async def finish_images(cb: CallbackQuery, state: FSMContext):
    await _show_confirm(cb.message, state)


async def _show_confirm(m, state):
    data  = await state.get_data()
    lines = ["📋 <b>خلاصه آگهی — تأیید نهایی</b>", ""]
    lines.append("📌 " + TYPE_MAP.get(data.get("listing_type", ""), "") + " — " + PROP_MAP.get(data.get("property_type", ""), ""))
    lines.append("📍 " + data.get("province", "") + " — " + data.get("city", ""))
    if data.get("district"):      lines.append("🏘 محله: "        + data["district"])
    if data.get("address"):       lines.append("📍 آدرس: "        + data["address"])
    if data.get("contact_phone"): lines.append("📞 تماس بازدید: " + data["contact_phone"])
    if data.get("area"):          lines.append("📐 متراژ: "       + str(data["area"]) + " متر")
    if data.get("bedrooms"):      lines.append("🛏 اتاق: "        + str(data["bedrooms"]))
    if data.get("price"):         lines.append("💵 قیمت: "        + fmt(data["price"]) + " تومان")
    if data.get("mortgage"):      lines.append("🔑 رهن: "         + fmt(data["mortgage"]) + " تومان")
    if data.get("rent"):          lines.append("🏠 اجاره: "       + fmt(data["rent"]) + " تومان")
    if data.get("facilities"):    lines.append("🏊 امکانات: "     + data["facilities"])
    if data.get("description"):   lines.append("📝 توضیحات: "     + data["description"])
    lines.append("📸 تصاویر: "   + str(len(data.get("images", []))) + " عدد")
    await state.set_state(ListingFSM.confirm)
    await m.answer("\n".join(lines), reply_markup=confirm_kb("submit"))


@router.callback_query(ListingFSM.confirm, F.data == "submit:no")
async def cancel_listing(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("❌ ثبت آگهی لغو شد.")


@router.callback_query(ListingFSM.confirm, F.data == "submit:yes")
async def submit_listing(cb: CallbackQuery, state: FSMContext, db_user=None):
    data = await state.get_data()
    await state.clear()
    async with AsyncSessionLocal() as db:
        lst = await create_listing(
            db,
            owner_id=db_user.telegram_id,
            listing_type=ListingType(data["listing_type"]),
            property_type=PropertyType(data["property_type"]),
            province=data.get("province", ""),
            city=data.get("city", ""),
            district=data.get("district"),
            address=data.get("address"),
            contact_phone=data.get("contact_phone"),
            area=data.get("area"),
            bedrooms=data.get("bedrooms"),
            price=data.get("price"),
            mortgage=data.get("mortgage"),
            rent=data.get("rent"),
            facilities=data.get("facilities"),
            description=data.get("description"),
        )
        for i, fid in enumerate(data.get("images", [])):
            await add_listing_image(db, lst.id, fid, order=i)
        review_raw = await get_setting(db, "review_group_id", "")
        review_gid = int(review_raw) if review_raw.lstrip("-").isdigit() else None

    await cb.message.edit_text(
        "✅ <b>آگهی با موفقیت ثبت شد!</b>\n"
        "🏷 کد: <code>" + lst.code + "</code>\n"
        "⏳ پس از تأیید ادمین منتشر می‌شود."
    )
    logger.info("New listing %s by %s", lst.code, db_user.telegram_id)

    if review_gid:
        caption = (
            "🔔 <b>آگهی جدید برای بررسی</b>\n"
            "🏷 کد: <code>" + lst.code + "</code>\n"
            "📌 " + TYPE_MAP.get(data["listing_type"], "") + " — " + PROP_MAP.get(data["property_type"], "") + "\n"
            "📍 " + data.get("province", "") + " — " + data.get("city", "") + "\n"
            + ("🏘 " + data["district"] + "\n" if data.get("district") else "")
            + ("📍 آدرس: " + data["address"] + "\n" if data.get("address") else "")
            + ("📞 تماس: " + data["contact_phone"] + "\n" if data.get("contact_phone") else "")
            + ("📐 " + str(data["area"]) + " متر\n" if data.get("area") else "")
            + ("💵 " + fmt(data["price"]) + " تومان\n" if data.get("price") else "")
            + ("🔑 رهن: " + fmt(data["mortgage"]) + "\n" if data.get("mortgage") else "")
            + ("🏠 اجاره: " + fmt(data["rent"]) + "\n" if data.get("rent") else "")
            + ("🏊 " + data["facilities"] + "\n" if data.get("facilities") else "")
            + ("📝 " + data["description"] + "\n" if data.get("description") else "")
            + "👤 " + db_user.full_name + " | 📞 " + db_user.phone
        )
        try:
            images = data.get("images", [])
            if images:
                sent = await cb.bot.send_photo(
                    review_gid, images[0], caption=caption,
                    reply_markup=review_group_kb(lst.id)
                )
            else:
                sent = await cb.bot.send_message(
                    review_gid, caption,
                    reply_markup=review_group_kb(lst.id)
                )
            async with AsyncSessionLocal() as db:
                await update_listing(db, lst.id, review_msg_id=sent.message_id)
        except Exception as e:
            logger.warning("review group send failed: %s", e)