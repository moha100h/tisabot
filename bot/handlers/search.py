from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.database import AsyncSessionLocal
from db.repository import search_listings
from db.models import ListingType, PropertyType
import logging

router = Router()
logger = logging.getLogger("search")

TYPE_MAP = {"sale": "فروش", "rent": "رهن/اجاره", "partnership": "مشارکت"}
PROP_MAP = {"apartment": "آپارتمان", "villa": "ویلا", "commercial": "تجاری",
            "land": "زمین", "office": "دفتر", "other": "سایر"}


class SearchFSM(StatesGroup):
    listing_type  = State()
    property_type = State()
    province      = State()
    city          = State()


def _lt_kb():
    b = InlineKeyboardBuilder()
    b.button(text="فروش",      callback_data="slt:sale")
    b.button(text="رهن/اجاره", callback_data="slt:rent")
    b.button(text="مشارکت",    callback_data="slt:partnership")
    b.button(text="همه",       callback_data="slt:all")
    b.adjust(2)
    return b.as_markup()


def _pt_kb():
    b = InlineKeyboardBuilder()
    b.button(text="آپارتمان", callback_data="spt:apartment")
    b.button(text="ویلا",     callback_data="spt:villa")
    b.button(text="تجاری",    callback_data="spt:commercial")
    b.button(text="زمین",     callback_data="spt:land")
    b.button(text="دفتر",     callback_data="spt:office")
    b.button(text="همه",      callback_data="spt:all")
    b.adjust(3)
    return b.as_markup()


@router.message(F.text == "🔍 جستجو")
async def start_search(msg: Message, state: FSMContext):
    await state.clear()
    await state.set_state(SearchFSM.listing_type)
    await msg.answer("🔍 <b>جستجوی ملک</b>\nنوع معامله:", reply_markup=_lt_kb())


@router.callback_query(SearchFSM.listing_type, F.data.startswith("slt:"))
async def got_lt(cb: CallbackQuery, state: FSMContext):
    val = cb.data.split(":")[1]
    await state.update_data(listing_type=None if val == "all" else val)
    await state.set_state(SearchFSM.property_type)
    await cb.message.edit_text("🏠 نوع ملک:", reply_markup=_pt_kb())


@router.callback_query(SearchFSM.property_type, F.data.startswith("spt:"))
async def got_pt(cb: CallbackQuery, state: FSMContext):
    val = cb.data.split(":")[1]
    await state.update_data(property_type=None if val == "all" else val)
    await state.set_state(SearchFSM.province)
    b = InlineKeyboardBuilder()
    b.button(text="⏭ همه استان‌ها", callback_data="skip_prov")
    await cb.message.edit_text("📍 استان را وارد کنید:", reply_markup=b.as_markup())


@router.callback_query(SearchFSM.province, F.data == "skip_prov")
async def skip_prov(cb: CallbackQuery, state: FSMContext):
    await state.update_data(province=None)
    await state.set_state(SearchFSM.city)
    b = InlineKeyboardBuilder()
    b.button(text="⏭ همه شهرها", callback_data="skip_city")
    await cb.message.edit_text("🏙 شهر را وارد کنید:", reply_markup=b.as_markup())


@router.message(SearchFSM.province, F.text)
async def got_prov(msg: Message, state: FSMContext):
    await state.update_data(province=msg.text.strip())
    await state.set_state(SearchFSM.city)
    b = InlineKeyboardBuilder()
    b.button(text="⏭ همه شهرها", callback_data="skip_city")
    await msg.answer("🏙 شهر را وارد کنید:", reply_markup=b.as_markup())


@router.callback_query(SearchFSM.city, F.data == "skip_city")
async def skip_city(cb: CallbackQuery, state: FSMContext):
    await state.update_data(city=None)
    await _do_search(cb.message, state)


@router.message(SearchFSM.city, F.text)
async def got_city(msg: Message, state: FSMContext):
    await state.update_data(city=msg.text.strip())
    await _do_search(msg, state)


async def _do_search(m, state):
    data = await state.get_data()
    await state.clear()
    lt = ListingType(data["listing_type"]) if data.get("listing_type") else None
    pt = PropertyType(data["property_type"]) if data.get("property_type") else None
    async with AsyncSessionLocal() as db:
        results = await search_listings(db, listing_type=lt, property_type=pt,
                                        province=data.get("province"), city=data.get("city"))
    if not results:
        await m.answer("📭 آگهی‌ای یافت نشد.")
        return
    await m.answer("✅ <b>" + str(len(results)) + " آگهی یافت شد:</b>")
    for lst in results:
        lines = ["🏷 <b>" + lst.code + "</b>"]
        lines.append("📌 " + TYPE_MAP.get(lst.listing_type.value, "") + " — " + PROP_MAP.get(lst.property_type.value, ""))
        lines.append("📍 " + lst.province + " — " + lst.city)
        if lst.area:     lines.append("📐 " + str(lst.area) + " متر")
        if lst.price:    lines.append("💵 " + f"{lst.price:,}" + " تومان")
        if lst.mortgage: lines.append("🔑 رهن: " + f"{lst.mortgage:,}" + " تومان")
        if lst.rent:     lines.append("🏠 اجاره: " + f"{lst.rent:,}" + " تومان")
        text = "\n".join(lines)
        if lst.images:
            await m.answer_photo(lst.images[0].file_id, caption=text)
        else:
            await m.answer(text)
