from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, PhotoSize
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.database import AsyncSessionLocal
from db.repository import (create_listing, add_listing_image,
    get_setting, update_listing)
from db.models import ListingType, PropertyType
from keyboards.main import listing_type_kb, property_type_kb, confirm_kb, skip_kb
import logging

router = Router()
logger = logging.getLogger("listing")

MAX_IMAGES   = 3
MAX_IMG_SIZE = 5 * 1024 * 1024


class ListingFSM(StatesGroup):
    type        = State()
    prop_type   = State()
    province    = State()
    city        = State()
    district    = State()
    address     = State()
    area        = State()
    bedrooms    = State()
    price       = State()
    mortgage    = State()
    rent        = State()
    land_area   = State()
    floors      = State()
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
    await msg.answer("📋 <b>ثبت آگهی جدید</b>

نوع معامله را انتخاب کنید:",
                     reply_markup=listing_type_kb())


@router.callback_query(ListingFSM.type, F.data.startswith("lt:"))
async def got_listing_type(cb: CallbackQuery, state: FSMContext):
    val = cb.data.split(":")[1]
    if val == "back":
        await state.clear()
        await cb.message.delete()
        return
    await state.update_data(listing_type=val)
    await state.set_state(ListingFSM.prop_type)
    await cb.message.edit_text("🏠 نوع ملک را انتخاب کنید:", reply_markup=property_type_kb())


@router.callback_query(ListingFSM.prop_type, F.data.startswith("pt:"))
async def got_prop_type(cb: CallbackQuery, state: FSMContext):
    val = cb.data.split(":")[1]
    if val == "back":
        await state.set_state(ListingFSM.type)
        await cb.message.edit_text("نوع معامله را انتخاب کنید:", reply_markup=listing_type_kb())
        return
    await state.update_data(property_type=val)
    await state.set_state(ListingFSM.province)
    await cb.message.edit_text("📍 <b>استان</b> ملک را وارد کنید:
<i>مثال: تهران</i>")


async def _ask(msg, state, next_state, question, skip_cb=None):
    await state.set_state(next_state)
    kb = skip_kb(skip_cb) if skip_cb else None
    await msg.answer(question, reply_markup=kb)


@router.message(ListingFSM.province, F.text)
async def got_province(msg: Message, state: FSMContext):
    await state.update_data(province=msg.text.strip())
    await _ask(msg, state, ListingFSM.city, "🏙 <b>شهر</b> را وارد کنید:")


@router.message(ListingFSM.city, F.text)
async def got_city(msg: Message, state: FSMContext):
    await state.update_data(city=msg.text.strip())
    await _ask(msg, state, ListingFSM.district,
               "🏘 <b>محله/منطقه</b> را وارد کنید:", skip_cb="skip_district")


@router.callback_query(ListingFSM.district, F.data == "skip_district")
async def skip_district(cb: CallbackQuery, state: FSMContext):
    await state.update_data(district=None)
    await state.set_state(ListingFSM.address)
    await cb.message.edit_text("📌 <b>آدرس تقریبی</b> را وارد کنید:", reply_markup=None)


@router.message(ListingFSM.district, F.text)
async def got_district(msg: Message, state: FSMContext):
    await state.update_data(district=msg.text.strip())
    await _ask(msg, state, ListingFSM.address,
               "📌 <b>آدرس تقریبی</b> را وارد کنید:", skip_cb="skip_address")


@router.callback_query(ListingFSM.address, F.data == "skip_address")
async def skip_address(cb: CallbackQuery, state: FSMContext):
    await state.update_data(address=None)
    await _next_after_address(cb.message, state)


@router.message(ListingFSM.address, F.text)
async def got_address(msg: Message, state: FSMContext):
    await state.update_data(address=msg.text.strip())
    await _next_after_address(msg, state)


async def _next_after_address(m, state):
    data = await state.get_data()
    if data.get("listing_type") == "partnership":
        await state.set_state(ListingFSM.land_area)
        await m.answer("📐 <b>مساحت زمین</b> (متر مربع) را وارد کنید:")
    else:
        await state.set_state(ListingFSM.area)
        await m.answer("📐 <b>متراژ</b> (متر مربع) را وارد کنید:")


@router.message(ListingFSM.land_area, F.text)
async def got_land_area(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("⚠️ عدد وارد کنید.")
        return
    await state.update_data(area=int(msg.text))
    await _ask(msg, state, ListingFSM.floors,
               "🏗 <b>تعداد طبقات مجاز</b> را وارد کنید:", skip_cb="skip_floors")


@router.callback_query(ListingFSM.floors, F.data == "skip_floors")
async def skip_floors(cb: CallbackQuery, state: FSMContext):
    await state.update_data(bedrooms=None)
    await _ask(cb.message, state, ListingFSM.description,
               "📝 <b>توضیحات</b> را وارد کنید:", skip_cb="skip_desc")


@router.message(ListingFSM.floors, F.text)
async def got_floors(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("⚠️ عدد وارد کنید.")
        return
    await state.update_data(bedrooms=int(msg.text))
    await _ask(msg, state, ListingFSM.description,
               "📝 <b>توضیحات</b> را وارد کنید:", skip_cb="skip_desc")


@router.message(ListingFSM.area, F.text)
async def got_area(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("⚠️ عدد وارد کنید.")
        return
    await state.update_data(area=int(msg.text))
    await _ask(msg, state, ListingFSM.bedrooms,
               "🛏 <b>تعداد اتاق خواب</b> را وارد کنید:", skip_cb="skip_bedrooms")


@router.callback_query(ListingFSM.bedrooms, F.data == "skip_bedrooms")
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
    lt = data.get("listing_type")
    if lt == "sale":
        await state.set_state(ListingFSM.price)
        await m.answer("💵 <b>قیمت کل</b> (تومان) را وارد کنید:")
    else:
        await state.set_state(ListingFSM.mortgage)
        await m.answer("🔑 <b>مبلغ رهن</b> (تومان) را وارد کنید:",
                       reply_markup=skip_kb("skip_mortgage"))


@router.message(ListingFSM.price, F.text)
async def got_price(msg: Message, state: FSMContext):
    val = msg.text.replace(",", "").replace("،", "")
    if not val.isdigit():
        await msg.answer("⚠️ عدد وارد کنید.")
        return
    await state.update_data(price=int(val))
    await _ask(msg, state, ListingFSM.facilities,
               "🏊 <b>امکانات</b> را وارد کنید:", skip_cb="skip_facilities")


@router.callback_query(ListingFSM.mortgage, F.data == "skip_mortgage")
async def skip_mortgage(cb: CallbackQuery, state: FSMContext):
    await state.update_data(mortgage=None)
    await state.set_state(ListingFSM.rent)
    await cb.message.edit_text("🏠 <b>مبلغ اجاره ماهانه</b> (تومان) را وارد کنید:")


@router.message(ListingFSM.mortgage, F.text)
async def got_mortgage(msg: Message, state: FSMContext):
    val = msg.text.replace(",", "").replace("،", "")
    if not val.isdigit():
        await msg.answer("⚠️ عدد وارد کنید.")
        return
    await state.update_data(mortgage=int(val))
    await _ask(msg, state, ListingFSM.rent,
               "🏠 <b>مبلغ اجاره ماهانه</b> (تومان) را وارد کنید:", skip_cb="skip_rent")


@router.callback_query(ListingFSM.rent, F.data == "skip_rent")
async def skip_rent(cb: CallbackQuery, state: FSMContext):
    await state.update_data(rent=None)
    await _ask(cb.message, state, ListingFSM.facilities,
               "🏊 <b>امکانات</b> را وارد کنید:", skip_cb="skip_facilities")


@router.message(ListingFSM.rent, F.text)
async def got_rent(msg: Message, state: FSMContext):
    val = msg.text.replace(",", "").replace("،", "")
    if not val.isdigit():
        await msg.answer("⚠️ عدد وارد کنید.")
        return
    await state.update_data(rent=int(val))
    await _ask(msg, state, ListingFSM.facilities,
               "🏊 <b>امکانات</b> را وارد کنید:", skip_cb="skip_facilities")


@router.callback_query(ListingFSM.facilities, F.data == "skip_facilities")
async def skip_facilities(cb: CallbackQuery, state: FSMContext):
    await state.update_data(facilities=None)
    await _ask(cb.message, state, ListingFSM.description,
               "📝 <b>توضیحات</b> را وارد کنید:", skip_cb="skip_desc")


@router.message(ListingFSM.facilities, F.text)
async def got_facilities(msg: Message, state: FSMContext):
    await state.update_data(facilities=msg.text.strip())
    await _ask(msg, state, ListingFSM.description,
               "📝 <b>توضیحات</b> را وارد کنید:", skip_cb="skip_desc")


@router.callback_query(ListingFSM.description, F.data == "skip_desc")
async def skip_desc(cb: CallbackQuery, state: FSMContext):
    await state.update_data(description=None)
    await _ask_images(cb.message, state)


@router.message(ListingFSM.description, F.text)
async def got_description(msg: Message, state: FSMContext):
    await state.update_data(description=msg.text.strip())
    await _ask_images(msg, state)


async def _ask_images(m, state):
    await state.set_state(ListingFSM.images)
    await state.update_data(images=[])
    b = InlineKeyboardBuilder()
    b.button(text="⏭ بدون تصویر ثبت کن", callback_data="skip_images")
    await m.answer(
        f"📸 <b>تصاویر ملک</b>

حداکثر {MAX_IMAGES} تصویر (هر تصویر حداکثر ۵ مگابایت)
"
        "تصاویر را یکی‌یکی ارسال کنید یا رد کنید:",
        reply_markup=b.as_markup()
    )


@router.message(ListingFSM.images, F.photo)
async def got_image(msg: Message, state: FSMContext):
    data = await state.get_data()
    images: list = data.get("images", [])
    photo: PhotoSize = msg.photo[-1]
    if photo.file_size and photo.file_size > MAX_IMG_SIZE:
        await msg.answer("⚠️ حجم تصویر بیشتر از ۵ مگابایت است.")
        return
    images.append(photo.file_id)
    await state.update_data(images=images)
    remaining = MAX_IMAGES - len(images)
    if remaining > 0:
        b = InlineKeyboardBuilder()
        b.button(text="✅ همین کافیه", callback_data="done_images")
        await msg.answer(
            f"✅ تصویر {len(images)} دریافت شد. می‌توانید {remaining} تصویر دیگر ارسال کنید.",
            reply_markup=b.as_markup()
        )
    else:
        await _show_confirm(msg, state)


@router.callback_query(ListingFSM.images, F.data.in_({"skip_images", "done_images"}))
async def finish_images(cb: CallbackQuery, state: FSMContext):
    await _show_confirm(cb.message, state)


async def _show_confirm(m, state):
    data = await state.get_data()
    TYPE_MAP = {"sale": "فروش", "rent": "رهن/اجاره", "partnership": "مشارکت"}
    PROP_MAP = {"apartment": "آپارتمان", "villa": "ویلا", "commercial": "تجاری",
                "land": "زمین", "office": "دفتر", "other": "سایر"}
    lines = [
        "📋 <b>خلاصه آگهی — تأیید نهایی</b>
",
        f"📌 نوع معامله: {TYPE_MAP.get(data.get('listing_type',''), '')}",
        f"🏠 نوع ملک: {PROP_MAP.get(data.get('property_type',''), '')}",
        f"📍 موقعیت: {data.get('province','')} — {data.get('city','')}",
    ]
    if data.get("district"):    lines.append(f"🏘 محله: {data['district']}")
    if data.get("area"):        lines.append(f"📐 متراژ: {data['area']:,} متر")
    if data.get("bedrooms"):    lines.append(f"🛏 اتاق: {data['bedrooms']}")
    if data.get("price"):       lines.append(f"💵 قیمت: {data['price']:,} تومان")
    if data.get("mortgage"):    lines.append(f"🔑 رهن: {data['mortgage']:,} تومان")
    if data.get("rent"):        lines.append(f"🏠 اجاره: {data['rent']:,} تومان")
    if data.get("facilities"):  lines.append(f"🏊 امکانات: {data['facilities']}")
    if data.get("description"): lines.append(f"📝 توضیحات: {data['description']}")
    lines.append(f"📸 تصاویر: {len(data.get('images', []))} عدد")
    await state.set_state(ListingFSM.confirm)
    await m.answer("
".join(lines), reply_markup=confirm_kb("submit"))


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
        # خواندن REVIEW_GROUP_ID از تنظیمات DB
        review_group_raw = await get_setting(db, "review_group_id", "")
        review_group_id = int(review_group_raw) if review_group_raw.lstrip("-").isdigit() else None

    await cb.message.edit_text(
        f"✅ <b>آگهی با موفقیت ثبت شد!</b>

"
        f"🏷 کد ملک: <code>{lst.code}</code>
"
        f"⏳ آگهی شما در صف بررسی قرار گرفت و پس از تأیید منتشر می‌شود."
    )
    logger.info(f"New listing {lst.code} by user {db_user.telegram_id}")

    if review_group_id:
        TYPE_MAP = {"sale": "فروش", "rent": "رهن/اجاره", "partnership": "مشارکت"}
        PROP_MAP = {"apartment": "آپارتمان", "villa": "ویلا", "commercial": "تجاری",
                    "land": "زمین", "office": "دفتر", "other": "سایر"}
        from keyboards.main import review_group_kb
        review_text = (
            f"🔔 <b>آگهی جدید برای بررسی</b>

"
            f"🏷 کد: <code>{lst.code}</code>
"
            f"📌 {TYPE_MAP.get(data['listing_type'],'')} — {PROP_MAP.get(data['property_type'],'')}
"
            f"📍 {data.get('province','')} — {data.get('city','')}
"
            f"👤 {db_user.full_name} | 📞 {db_user.phone}"
        )
        try:
            images = data.get("images", [])
            if images:
                sent = await cb.bot.send_photo(review_group_id, images[0],
                    caption=review_text, reply_markup=review_group_kb(lst.id))
            else:
                sent = await cb.bot.send_message(review_group_id, review_text,
                    reply_markup=review_group_kb(lst.id))
            async with AsyncSessionLocal() as db:
                await update_listing(db, lst.id, review_msg_id=sent.message_id)
        except Exception as e:
            logger.warning(f"Could not send to review group: {e}")
