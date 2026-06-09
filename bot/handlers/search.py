from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.database import AsyncSessionLocal
from db.repository import search_listings, get_listing
from db.models import ListingType, PropertyType
from keyboards.main import listing_card_kb
import logging

router = Router()
logger = logging.getLogger("search")


class SearchFSM(StatesGroup):
    listing_type  = State()
    property_type = State()
    province      = State()
    city          = State()
    min_price     = State()
    max_price     = State()


def _listing_type_kb():
    b = InlineKeyboardBuilder()
    b.button(text="🏷 فروش",           callback_data="slt:sale")
    b.button(text="🏠 رهن/اجاره",      callback_data="slt:rent")
    b.button(text="🤝 مشارکت",         callback_data="slt:partnership")
    b.button(text="🔍 همه",            callback_data="slt:all")
    b.adjust(2, 2)
    return b.as_markup()


def _prop_type_kb():
    b = InlineKeyboardBuilder()
    for label, val in [("🏢 آپارتمان","apartment"),("🏡 ویلا","villa"),
                       ("🏪 تجاری","commercial"),("🌿 زمین","land"),
                       ("🏬 دفتر","office"),("📦 سایر","other"),("🔍 همه","all")]:
        b.button(text=label, callback_data=f"spt:{val}")
    b.adjust(2, 2, 2, 1)
    return b.as_markup()


@router.message(F.text == "🔍 جستجوی ملک")
async def start_search(msg: Message, state: FSMContext):
    await state.clear()
    await state.set_state(SearchFSM.listing_type)
    await msg.answer("🔍 <b>جستجوی ملک</b>

نوع معامله:", reply_markup=_listing_type_kb())


@router.callback_query(SearchFSM.listing_type, F.data.startswith("slt:"))
async def got_slt(cb: CallbackQuery, state: FSMContext):
    val = cb.data.split(":")[1]
    await state.update_data(listing_type=None if val == "all" else val)
    await state.set_state(SearchFSM.property_type)
    await cb.message.edit_text("🏠 نوع ملک:", reply_markup=_prop_type_kb())


@router.callback_query(SearchFSM.property_type, F.data.startswith("spt:"))
async def got_spt(cb: CallbackQuery, state: FSMContext):
    val = cb.data.split(":")[1]
    await state.update_data(property_type=None if val == "all" else val)
    await state.set_state(SearchFSM.province)
    b = InlineKeyboardBuilder()
    b.button(text="⏭ همه استان‌ها", callback_data="skip_province")
    await cb.message.edit_text("📍 استان را وارد کنید:", reply_markup=b.as_markup())


@router.callback_query(SearchFSM.province, F.data == "skip_province")
async def skip_province(cb: CallbackQuery, state: FSMContext):
    await state.update_data(province=None)
    await _ask_city(cb.message, state)


@router.message(SearchFSM.province, F.text)
async def got_sprovince(msg: Message, state: FSMContext):
    await state.update_data(province=msg.text.strip())
    await _ask_city(msg, state)


async def _ask_city(msg_or_cb, state: FSMContext):
    await state.set_state(SearchFSM.city)
    b = InlineKeyboardBuilder()
    b.button(text="⏭ همه شهرها", callback_data="skip_city")
    await msg_or_cb.answer("🏙 شهر را وارد کنید:", reply_markup=b.as_markup())


@router.callback_query(SearchFSM.city, F.data == "skip_city")
async def skip_city(cb: CallbackQuery, state: FSMContext):
    await state.update_data(city=None)
    await _do_search(cb.message, state, cb.from_user.id)


@router.message(SearchFSM.city, F.text)
async def got_scity(msg: Message, state: FSMContext):
    await state.update_data(city=msg.text.strip())
    await _do_search(msg, state, msg.from_user.id)


async def _do_search(msg_or_cb, state: FSMContext, user_id: int):
    data = await state.get_data()
    await state.clear()
    filters = {k: v for k, v in data.items() if v is not None}
    if filters.get("listing_type"):
        filters["listing_type"] = ListingType(filters["listing_type"])
    if filters.get("property_type"):
        filters["property_type"] = PropertyType(filters["property_type"])

    async with AsyncSessionLocal() as db:
        results = await search_listings(db, **filters)

    if not results:
        await msg_or_cb.answer("📭 آگهی‌ای با این مشخصات یافت نشد.")
        return

    await msg_or_cb.answer(f"🔍 <b>{len(results)} آگهی یافت شد:</b>")
    TYPE_MAP = {"sale": "فروش", "rent": "رهن/اجاره", "partnership": "مشارکت"}
    PROP_MAP = {"apartment": "آپارتمان", "villa": "ویلا", "commercial": "تجاری",
                "land": "زمین", "office": "دفتر", "other": "سایر"}

    for lst in results[:10]:
        lines = [
            f"🏷 <b>کد:</b> {lst.code}",
            f"📌 {TYPE_MAP.get(lst.listing_type.value,'')} — {PROP_MAP.get(lst.property_type.value,'')}",
            f"📍 {lst.province} — {lst.city}" + (f" — {lst.district}" if lst.district else ""),
        ]
        if lst.area:     lines.append(f"📐 {lst.area:,} متر")
        if lst.bedrooms: lines.append(f"🛏 {lst.bedrooms} اتاق")
        if lst.price:    lines.append(f"💵 {lst.price:,} تومان")
        if lst.mortgage: lines.append(f"🔑 رهن: {lst.mortgage:,}")
        if lst.rent:     lines.append(f"🏠 اجاره: {lst.rent:,}")
        if lst.description: lines.append(f"📝 {lst.description[:100]}")

        is_owner = (lst.owner_id == user_id)
        kb = listing_card_kb(lst.id, lst.owner.phone if lst.owner else "—", is_owner=is_owner)
        text = "
".join(lines)

        if lst.images:
            await msg_or_cb.answer_photo(lst.images[0].file_id, caption=text, reply_markup=kb)
        else:
            await msg_or_cb.answer(text, reply_markup=kb)
