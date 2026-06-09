from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from db.database import AsyncSessionLocal
from db.repository import get_user, create_user, update_user
from db.models import UserRole
from keyboards.main import main_menu, contact_kb
from config import ADMIN_ID
import logging

router = Router()
logger = logging.getLogger("register")


class RegisterFSM(StatesGroup):
    waiting_contact  = State()
    waiting_fullname = State()


@router.message(F.text == "/start")
async def cmd_start(msg: Message, state: FSMContext, db_user=None):
    if db_user:
        # اگر ادمین هست ولی هنوز SUPER نشده، الان ست کن
        if msg.from_user.id == ADMIN_ID and db_user.role != UserRole.SUPER:
            async with AsyncSessionLocal() as db:
                await update_user(db, ADMIN_ID, role=UserRole.SUPER)
            db_user.role = UserRole.SUPER
            logger.info("Admin %s promoted to SUPER on /start", ADMIN_ID)
        await msg.answer(
            "👋 خوش آمدید <b>" + db_user.full_name + "</b>!\n"
            "از منوی زیر انتخاب کنید:",
            reply_markup=main_menu()
        )
        return
    await state.set_state(RegisterFSM.waiting_contact)
    await msg.answer(
        "👋 به ربات مدیریت املاک خوش آمدید!\n\n"
        "برای ثبت‌نام، لطفاً شماره تماس خود را به اشتراک بگذارید:",
        reply_markup=contact_kb()
    )


@router.message(RegisterFSM.waiting_contact, F.contact)
async def got_contact(msg: Message, state: FSMContext):
    contact = msg.contact
    if contact.user_id != msg.from_user.id:
        await msg.answer("⚠️ لطفاً شماره خودتان را ارسال کنید.")
        return
    await state.update_data(phone=contact.phone_number)
    await state.set_state(RegisterFSM.waiting_fullname)
    await msg.answer(
        "✅ شماره دریافت شد.\nلطفاً نام و نام خانوادگی خود را وارد کنید:",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(RegisterFSM.waiting_contact, F.text == "❌ انصراف")
async def cancel_register(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("❌ ثبت‌نام لغو شد.", reply_markup=ReplyKeyboardRemove())


@router.message(RegisterFSM.waiting_fullname, F.text)
async def got_fullname(msg: Message, state: FSMContext):
    full_name = msg.text.strip()
    if len(full_name) < 3:
        await msg.answer("⚠️ نام حداقل باید ۳ کاراکتر باشد.")
        return
    data  = await state.get_data()
    phone = data.get("phone", "")
    await state.clear()
    async with AsyncSessionLocal() as db:
        user = await create_user(
            db,
            telegram_id=msg.from_user.id,
            full_name=full_name,
            phone=phone,
            username=msg.from_user.username
        )
        # اگر ادمین تازه ثبت‌نام کرد، فوری SUPER بشه
        if msg.from_user.id == ADMIN_ID:
            await update_user(db, ADMIN_ID, role=UserRole.SUPER)
            user.role = UserRole.SUPER
            logger.info("Admin %s registered and set to SUPER", ADMIN_ID)

    await msg.answer(
        "🎉 ثبت‌نام با موفقیت انجام شد!\n"
        "نام: <b>" + user.full_name + "</b>\n"
        "شماره: " + user.phone,
        reply_markup=main_menu()
    )
    logger.info("New user: %s - %s", user.telegram_id, user.full_name)
