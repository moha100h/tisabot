from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, PhotoSize
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.database import AsyncSessionLocal
from db.repository import create_listing, add_listing_image, get_setting, update_listing
from db.models import ListingType, PropertyType
from keyboards.main import listing_type_kb, property_type_kb, confirm_kb, review_group_kb
import logging

router = Router()
logger = logging.getLogger("listing")

MAX_IMAGES = 3
TYPE_MAP = {"sale": "فروش", "rent": "رهن/اجاره", "partnership": "مشارکت"}
PROP_MAP = {"apartment": "آپارتمان", "villa": "ویلا", "commercial": "تجاری",
            "land": "زمین", "office": "دفتر", "other": "سایر"}


class ListingFSM(StatesGroup):
    type        = State()
    prop_type   = State()
    province    = State()
    city        = State()
    district    = State()
    area        = State()
    bedrooms    = State()
    price       = State()
    mortgage    = State()
    rent        = State()
    facilities  = State()
    description = State()
    images      = State()
    confirm     = State()


@router.message(F.text == "🏠 ثبت آگهی")
async def start_listing(msg: Message, state: FSMContext, db_user=None):
    if not db_user:
        await msg.answer("⚠️ ابتدا ثبت‌نام کنید. /start")
        return
    await state.clear()
    await state.set_state(ListingFSM.type)
    await msg.answer("📋 <b>ثبت آگهی جدید</b>\nنوع معامله را انتخاب کنید:",
                     reply_markup=listing_type_kb())


@router.callback_query(ListingFSM.type, F.data.startswith("lt:"))
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
        await state.set_state(ListingFSM.type)
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
    b = InlineKeyboardBuilder()
    b.button(text="⏭ رد کردن", callback_data="skip:district")
    await msg.answer("🏘 <b>محله</b> را وارد کنید:", reply_markup=b.as_markup())


@router.callback_query(F.data == "skip:district")
async def skip_district(cb: CallbackQuery, state: FSMContext):
    await state.update_data(district=None)
    await state.set_state(ListingFSM.area)
    await cb.message.edit_text("📐 <b>متراژ</b> (متر مربع) را وارد کنید:")


@router.message(ListingFSM.district, F.text)
async def got_district(msg: Message, state: FSMContext):
    await state.update_data(district=msg.text.strip())
    await state.set_state(ListingFSM.area)
    await msg.answer("📐 <b>متراژ</b> (متر مربع) را وارد کنید:")


@router.message(ListingFSM.area, F.text)
async def got_area(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("⚠️ عدد وارد کنید.")
        return
    await state.update_data(area=int(msg.text))
    await state.set_state(ListingFSM.bedrooms)
    b = InlineKeyboardBuilder()
    b.button(text="⏭ رد کردن", callback_data="skip:bedrooms")
    await msg.answer("🛏 <b>تعداد اتاق خواب</b>:", reply_markup=b.as_markup())


@router.callback_query(F.data == "skip:bedrooms")
async def skip_bedrooms(cb: CallbackQuery, state: FSMContext):
    await state.update_data(bedrooms=None)
    await _price_step(cb.message, state)


@router.message(ListingFSM.bedrooms, F.text)
async def got_bedrooms(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("⚠️ عدد وارد کنید.")
        return
    await state.update_data(bedrooms=int(msg.text))
    await _price_step(msg, state)


async def _price_step(m, state):
    data = await state.get_data()
    if data.get("listing_type") == "sale":
        await state.set_state(ListingFSM.price)
        await m.answer("💵 <b>قیمت کل</b> (تومان):")
    else:
        await state.set_state(ListingFSM.mortgage)
        b = InlineKeyboardBuilder()
        b.button(text="⏭ رد کردن", callback_data="skip:mortgage")
        await m.answer("🔑 <b>مبلغ رهن</b> (تومان):", reply_markup=b.as_markup())


@router.message(ListingFSM.price, F.text)
async def got_price(msg: Message, state: FSMContext):
    val = msg.text.replace(",", "").replace("،", "")
    if not val.isdigit():
        await msg.answer("⚠️ عدد وارد کنید.")
        return
    await state.update_data(price=int(val))
    await _facilities_step(msg, state)


@router.callback_query(F.data == "skip:mortgage")
async def skip_mortgage(cb: CallbackQuery, state: FSMContext):
    await state.update_data(mortgage=None)
    await state.set_state(ListingFSM.rent)
    b = InlineKeyboardBuilder()
    b.button(text="⏭ رد کردن", callback_data="skip:rent")
    await cb.message.edit_text("🏠 <b>اجاره ماهانه</b> (تومان):", reply_markup=b.as_markup())


@router.message(ListingFSM.mortgage, F.text)
async def got_mortgage(msg: Message, state: FSMContext):
    val = msg.text.replace(",", "").replace("،", "")
    if not val.isdigit():
        await msg.answer("⚠️ عدد وارد کنید.")
        return
    await state.update_data(mortgage=int(val))
    await state.set_state(ListingFSM.rent)
    b = InlineKeyboardBuilder()
    b.button(text="⏭ رد کردن", callback_data="skip:rent")
    await msg.answer("🏠 <b>اجاره ماهانه</b> (تومان):", reply_markup=b.as_markup())


@router.callback_query(F.data == "skip:rent")
async def skip_rent(cb: CallbackQuery, state: FSMContext):
    await state.update_data(rent=None)
    await _facilities_step(cb.message, state)


@router.message(ListingFSM.rent, F.text)
async def got_rent(msg: Message, state: FSMContext):
    val = msg.text.replace(",", "").replace("،", "")
    if not val.isdigit():
        await msg.answer("⚠️ عدد وارد کنید.")
        return
    await state.update_data(rent=int(val))
    await _facilities_step(msg, state)


async def _facilities_step(m, state):
    await state.set_state(ListingFSM.facilities)
    b = InlineKeyboardBuilder()
    b.button(text="⏭ رد کردن", callback_data="skip:facilities")
    await m.answer("🏊 <b>امکانات</b>:", reply_markup=b.as_markup())


@router.callback_query(F.data == "skip:facilities")
async def skip_facilities(cb: CallbackQuery, state: FSMContext):
    await state.update_data(facilities=None)
    await _desc_step(cb.message, state)


@router.message(ListingFSM.facilities, F.text)
async def got_facilities(msg: Message, state: FSMContext):
    await state.update_data(facilities=msg.text.strip())
    await _desc_step(msg, state)


async def _desc_step(m, state):
    await state.set_state(ListingFSM.description)
    b = InlineKeyboardBuilder()
    b.button(text="⏭ رد کردن", callback_data="skip:desc")
    await m.answer("📝 <b>توضیحات</b>:", reply_markup=b.as_markup())


@router.callback_query(F.data == "skip:desc")
async def skip_desc(cb: CallbackQuery, state: FSMContext):
    await state.update_data(description=None)
    await _images_step(cb.message, state)


@router.message(ListingFSM.description, F.text)
async def got_desc(msg: Message, state: FSMContext):
    await state.update_data(description=msg.text.strip())
    await _images_step(msg, state)


async def _images_step(m, state):
    await state.set_state(ListingFSM.images)
    await state.update_data(images=[])
    b = InlineKeyboardBuilder()
    b.button(text="⏭ بدون تصویر", callback_data="skip:images")
    await m.answer(
        "📸 <b>تصاویر ملک</b> (حداکثر " + str(MAX_IMAGES) + " عدد)\nیکی‌یکی ارسال کنید:",
        reply_markup=b.as_markup()
    )


@router.message(ListingFSM.images, F.photo)
async def got_image(msg: Message, state: FSMContext):
    data = await state.get_data()
    images = data.get("images", [])
    photo: PhotoSize = msg.photo[-1]
    if photo.file_size and photo.file_size > 5 * 1024 * 1024:
        await msg.answer("⚠️ حجم تصویر بیشتر از ۵ مگابایت است.")
        return
    images.append(photo.file_id)
    await state.update_data(images=images)
    if len(images) < MAX_IMAGES:
        b = InlineKeyboardBuilder()
        b.button(text="✅ همین کافیه", callback_data="skip:images")
        await msg.answer("✅ تصویر " + str(len(images)) + " دریافت شد.", reply_markup=b.as_markup())
    else:
        await _confirm_step(msg, state)


@router.callback_query(F.data == "skip:images")
async def finish_images(cb: CallbackQuery, state: FSMContext):
    await _confirm_step(cb.message, state)


async def _confirm_step(m, state):
    data = await state.get_data()
    lines = ["📋 <b>خلاصه آگهی — تأیید نهایی</b>", ""]
    lines.append("📌 " + TYPE_MAP.get(data.get("listing_type", ""), "") + " — " + PROP_MAP.get(data.get("property_type", ""), ""))
    lines.append("📍 " + data.get("province", "") + " — " + data.get("city", ""))
    if data.get("district"):    lines.append("🏘 " + data["district"])
    if data.get("area"):        lines.append("📐 " + f"{data['area']:,}" + " متر")
    if data.get("bedrooms"):    lines.append("🛏 " + str(data["bedrooms"]) + " اتاق")
    if data.get("price"):       lines.append("💵 " + f"{data['price']:,}" + " تومان")
    if data.get("mortgage"):    lines.append("🔑 رهن: " + f"{data['mortgage']:,}" + " تومان")
    if data.get("rent"):        lines.append("🏠 اجاره: " + f"{data['rent']:,}" + " تومان")
    if data.get("facilities"):  lines.append("🏊 " + data["facilities"])
    if data.get("description"): lines.append("📝 " + data["description"])
    lines.append("📸 " + str(len(data.get("images", []))) + " تصویر")
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
        "✅ <b>آگهی ثبت شد!</b>\n"
        "🏷 کد: <code>" + lst.code + "</code>\n"
        "⏳ پس از تأیید منتشر می‌شود."
    )

    if review_gid:
        text = (
            "🔔 <b>آگهی جدید برای بررسی</b>\n"
            "🏷 کد: <code>" + lst.code + "</code>\n"
            "📌 " + TYPE_MAP.get(data["listing_type"], "") + " — " + PROP_MAP.get(data["property_type"], "") + "\n"
            "📍 " + data.get("province", "") + " — " + data.get("city", "") + "\n"
            "👤 " + db_user.full_name + " | 📞 " + db_user.phone
        )
        try:
            imgs = data.get("images", [])
            if imgs:
                sent = await cb.bot.send_photo(review_gid, imgs[0], caption=text,
                                               reply_markup=review_group_kb(lst.id))
            else:
                sent = await cb.bot.send_message(review_gid, text,
                                                 reply_markup=review_group_kb(lst.id))
            async with AsyncSessionLocal() as db:
                await update_listing(db, lst.id, review_msg_id=sent.message_id)
        except Exception as e:
            logger.warning("review group send failed: %s", e)
