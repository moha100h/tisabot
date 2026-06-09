from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from db.database import AsyncSessionLocal
from db.repository import get_user, create_user
from keyboards.main import main_menu, contact_kb
import logging

router = Router()
logger = logging.getLogger("register")


class RegisterFSM(StatesGroup):
    waiting_contact  = State()
    waiting_fullname = State()
    waiting_phone    = State()


@router.message(F.text == "/start")
async def cmd_start(msg: Message, state: FSMContext, db_user=None):
    if db_user:
        await msg.answer(
            f"👋 خوش آمدید <b>{db_user.full_name}</b>!
"
            "از منوی زیر انتخاب کنید:",
            reply_markup=main_menu()
        )
        return
    await state.set_state(RegisterFSM.waiting_contact)
    await msg.answer(
        "👋 به ربات مدیریت املاک خوش آمدید!

"
        "برای ثبت‌نام، لطفاً شماره تماس خود را به اشتراک بگذارید:",
        reply_markup=contact_kb()
    )


@router.message(RegisterFSM.waiting_contact, F.contact)
async def got_contact(msg: Message, state: FSMContext):
    contact = msg.contact
    if contact.user_id != msg.from_user.id:
        await msg.answer("⚠️ لطفاً شماره خودتان را ارسال کنید.")
        return
    await state.update_data(phone_tg=contact.phone_number)
    await state.set_state(RegisterFSM.waiting_fullname)
    await msg.answer("✅ شماره دریافت شد.

لطفاً نام و نام خانوادگی خود را وارد کنید:",
                     reply_markup=ReplyKeyboardRemove())


@router.message(RegisterFSM.waiting_contact, F.text == "❌ انصراف")
async def cancel_register(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("❌ ثبت‌نام لغو شد.", reply_markup=ReplyKeyboardRemove())


@router.message(RegisterFSM.waiting_fullname, F.text)
async def got_fullname(msg: Message, state: FSMContext):
    name = msg.text.strip()
    if len(name) < 3:
        await msg.answer("⚠️ نام باید حداقل ۳ کاراکتر باشد.")
        return
    await state.update_data(full_name=name)
    await state.set_state(RegisterFSM.waiting_phone)
    await msg.answer(
        "📞 لطفاً شماره تماس مستقیم خود را وارد کنید:
"
        "<i>(برای تماس مستقیم توسط خریداران/مستأجران)</i>"
    )


@router.message(RegisterFSM.waiting_phone, F.text)
async def got_phone(msg: Message, state: FSMContext):
    phone = msg.text.strip().replace(" ", "")
    if not (phone.startswith(("09", "+98", "0098")) and len(phone) >= 10):
        await msg.answer("⚠️ شماره تماس معتبر نیست. مثال: 09123456789")
        return
    data = await state.get_data()
    async with AsyncSessionLocal() as db:
        user = await create_user(
            db,
            telegram_id=msg.from_user.id,
            full_name=data["full_name"],
            phone=phone,
            username=msg.from_user.username,
        )
    await state.clear()
    await msg.answer(
        f"🎉 ثبت‌نام با موفقیت انجام شد!

"
        f"👤 نام: <b>{user.full_name}</b>
"
        f"📞 تلفن: <b>{user.phone}</b>

"
        "از منوی زیر انتخاب کنید:",
        reply_markup=main_menu()
    )
    logger.info(f"New user registered: {user.telegram_id} — {user.full_name}")
