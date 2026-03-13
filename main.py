import asyncio
import re
import time
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

from config import BOT_TOKEN, ADMIN_IDS

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())


class OrderForm(StatesGroup):
    waiting_continue = State()
    waiting_start_form = State()
    waiting_order_id = State()
    waiting_fullname = State()
    waiting_country = State()
    waiting_city = State()
    waiting_address = State()
    waiting_confirmation = State()


COUNTRIES = {
    "🇺🇿 Ўзбекистон": [
        "Тошкент", "Самарқанд", "Бухоро", "Андижон",
        "Наманган", "Фарғона", "Нукус"
    ],
    "🇰🇿 Қозоғистон": [
        "Астана", "Олмаота", "Чимкент", "Қарағанда", "Туркистон"
    ],
    "🇰🇬 Қирғизистон": [
        "Бишкек", "Ўш", "Жалолобод"
    ],
    "🇹🇯 Тожикистон": [
        "Душанбе", "Хўжанд", "Бохтар"
    ],
    "🇹🇲 Туркманистон": [
        "Ашхобод", "Туркманобод", "Дашоғуз"
    ]
}

PENDING_REQUESTS = {}


def continue_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="▶️ Давом этиш")]
        ],
        resize_keyboard=True
    )


def start_form_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Буюртма маълумотларини киритиш")]
        ],
        resize_keyboard=True
    )


def countries_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇺🇿 Ўзбекистон"), KeyboardButton(text="🇰🇿 Қозоғистон")],
            [KeyboardButton(text="🇰🇬 Қирғизистон"), KeyboardButton(text="🇹🇯 Тожикистон")],
            [KeyboardButton(text="🇹🇲 Туркманистон")]
        ],
        resize_keyboard=True
    )


def cities_keyboard(country: str):
    cities = COUNTRIES.get(country, [])
    rows = []
    row = []

    for city in cities:
        row.append(KeyboardButton(text=city))
        if len(row) == 2:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    rows.append([KeyboardButton(text="⬅️ Давлатни ўзгартириш")])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True
    )


def confirmation_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Тасдиқлаш"), KeyboardButton(text="✏️ Ўзгартириш")]
        ],
        resize_keyboard=True
    )


def admin_inline_keyboard(request_id: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Тасдиқлаш",
                    callback_data=f"approve:{request_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Бекор қилиш",
                    callback_data=f"reject:{request_id}"
                )
            ]
        ]
    )


def is_valid_order_id(order_id: str) -> bool:
    return bool(re.fullmatch(r"\d{7}", order_id))


def is_valid_fullname(fullname: str) -> bool:
    parts = fullname.split()
    return len(parts) >= 2 and all(len(part) >= 2 for part in parts)


def is_valid_address(address: str) -> bool:
    return len(address.strip()) >= 10


def build_summary(data: dict) -> str:
    return (
        "📋 <b>Илтимос, киритилган маълумотларни текширинг:</b>\n\n"
        f"🆔 <b>Буюртма ID:</b> {data['order_id']}\n"
        f"👤 <b>Исм-фамилия:</b> {data['fullname']}\n"
        f"🌍 <b>Давлат:</b> {data['country']}\n"
        f"🏙 <b>Шаҳар:</b> {data['city']}\n"
        f"📍 <b>Манзил:</b> {data['address']}\n\n"
        "❓ <b>Барча маълумотлар тўғрими?</b>"
    )


def build_admin_text(data: dict, user: Message) -> str:
    username = f"@{user.from_user.username}" if user.from_user.username else "Йўқ"
    return (
        "🚨 <b>Янги етказиб бериш сўрови!</b>\n\n"
        f"🆔 <b>Буюртма ID:</b> {data['order_id']}\n"
        f"👤 <b>Исм-фамилия:</b> {data['fullname']}\n"
        f"🌍 <b>Давлат:</b> {data['country']}\n"
        f"🏙 <b>Шаҳар:</b> {data['city']}\n"
        f"📍 <b>Манзил:</b> {data['address']}\n\n"
        f"👤 <b>Telegram:</b> {username}\n"
        f"🆔 <b>User ID:</b> <code>{user.from_user.id}</code>"
    )


@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    text = (
        "👋 <b>Ассалому алайкум!</b>\n\n"
        "📦 Ушбу бот орқали сиз буюртма қилинган маҳсулот учун\n"
        "🚚 етказиб бериш маълумотларини юборишингиз мумкин.\n\n"
        "Сиздан қуйидаги маълумотлар сўралади:\n\n"
        "🆔 Буюртма ID рақами\n"
        "👤 Буюртма эгасининг исм-фамилияси\n"
        "🌍 Етказиб бериш давлати\n"
        "🏙 Шаҳар\n"
        "📍 Аниқ манзил\n\n"
        "⚠️ Илтимос, барча маълумотларни тўғри киритинг.\n\n"
        "Давом этиш учун қуйидаги тугмани босинг."
    )
    await message.answer(text, reply_markup=continue_keyboard())
    await state.set_state(OrderForm.waiting_continue)


@dp.message(OrderForm.waiting_continue, F.text == "▶️ Давом этиш")
async def continue_handler(message: Message, state: FSMContext):
    text = (
        "📌 <b>Маълумотларни киритишдан олдин қуйидагиларга эътибор беринг:</b>\n\n"
        "1️⃣ Буюртма ID <b>7 хонали</b> бўлиши керак\n"
        "2️⃣ Исм-фамилия <b>тўлиқ ёзилиши керак</b>\n"
        "3️⃣ Давлат ва шаҳар <b>тугмалар орқали танланади</b>\n"
        "4️⃣ Кейин <b>аниқ манзил</b> киритилади\n"
        "5️⃣ Барча маълумотлар <b>тасдиқлангандан кейин админга юборилади</b>\n\n"
        "Тайёр бўлсангиз, қуйидаги тугмани босинг."
    )
    await message.answer(text, reply_markup=start_form_keyboard())
    await state.set_state(OrderForm.waiting_start_form)


@dp.message(OrderForm.waiting_continue)
async def wrong_continue_handler(message: Message):
    await message.answer("⚠️ Илтимос, <b>▶️ Давом этиш</b> тугмасини босинг.")


@dp.message(OrderForm.waiting_start_form, F.text == "📝 Буюртма маълумотларини киритиш")
async def start_form_handler(message: Message, state: FSMContext):
    text = (
        "🆔 <b>Қайси ID бўйича буюртма қилгансиз?</b>\n\n"
        "Илтимос, <b>буюртма ID рақамини киритинг.</b>\n\n"
        "📌 <b>Намуна:</b>\n"
        "<code>0012345</code>\n\n"
        "⚠️ Буюртма ID <b>7 та рақамдан иборат бўлиши керак.</b>"
    )
    await message.answer(text, reply_markup=ReplyKeyboardRemove())
    await state.set_state(OrderForm.waiting_order_id)


@dp.message(OrderForm.waiting_start_form)
async def wrong_start_form_handler(message: Message):
    await message.answer("⚠️ Илтимос, <b>📝 Буюртма маълумотларини киритиш</b> тугмасини босинг.")


@dp.message(OrderForm.waiting_order_id)
async def order_id_handler(message: Message, state: FSMContext):
    order_id = message.text.strip()

    if not is_valid_order_id(order_id):
        await message.answer(
            "⚠️ <b>Буюртма ID нотўғри киритилди.</b>\n\n"
            "Илтимос, <b>7 хонали ID</b> киритинг.\n\n"
            "📌 <b>Намуна:</b>\n"
            "<code>0012345</code>"
        )
        return

    await state.update_data(order_id=order_id)
    await message.answer(
        "👤 <b>Буюртма эгасининг исм-фамилиясини киритинг.</b>\n\n"
        "📌 <b>Намуна:</b>\n"
        "Али Валиев"
    )
    await state.set_state(OrderForm.waiting_fullname)


@dp.message(OrderForm.waiting_fullname)
async def fullname_handler(message: Message, state: FSMContext):
    fullname = message.text.strip()

    if not is_valid_fullname(fullname):
        await message.answer(
            "⚠️ Илтимос, <b>исм ва фамилияни тўлиқ киритинг.</b>\n\n"
            "📌 <b>Намуна:</b>\n"
            "Али Валиев"
        )
        return

    await state.update_data(fullname=fullname)
    await message.answer(
        "🌍 <b>Етказиб бериш давлатини танланг:</b>",
        reply_markup=countries_keyboard()
    )
    await state.set_state(OrderForm.waiting_country)


@dp.message(OrderForm.waiting_country)
async def country_handler(message: Message, state: FSMContext):
    country = message.text.strip()

    if country not in COUNTRIES:
        await message.answer("⚠️ Илтимос, давлатни <b>тугмалар орқали танланг.</b>")
        return

    await state.update_data(country=country)
    await message.answer(
        "🏙 <b>Етказиб бериш шаҳарини танланг:</b>",
        reply_markup=cities_keyboard(country)
    )
    await state.set_state(OrderForm.waiting_city)


@dp.message(OrderForm.waiting_city, F.text == "⬅️ Давлатни ўзгартириш")
async def change_country_handler(message: Message, state: FSMContext):
    await message.answer(
        "🌍 <b>Етказиб бериш давлатини қайта танланг:</b>",
        reply_markup=countries_keyboard()
    )
    await state.set_state(OrderForm.waiting_country)


@dp.message(OrderForm.waiting_city)
async def city_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    country = data.get("country")
    city = message.text.strip()

    if city not in COUNTRIES.get(country, []):
        await message.answer("⚠️ Илтимос, шаҳарни <b>тугмалар орқали танланг.</b>")
        return

    await state.update_data(city=city)
    await message.answer(
        "📍 <b>Етказиб бериш учун аниқ манзилни киритинг.</b>\n\n"
        "📌 <b>Намуна:</b>\n"
        "Юнусобод тумани, 12-квартал, 45-уй, 12-хонадон\n\n"
        "ёки\n\n"
        "Абай кўчаси 17-уй, 24-хонадон"
    )
    await state.set_state(OrderForm.waiting_address)


@dp.message(OrderForm.waiting_address)
async def address_handler(message: Message, state: FSMContext):
    address = message.text.strip()

    if not is_valid_address(address):
        await message.answer(
            "⚠️ Илтимос, манзилни <b>аниқроқ киритинг.</b>\n\n"
            "📌 <b>Намуна:</b>\n"
            "Юнусобод тумани, 12-квартал, 45-уй, 12-хонадон"
        )
        return

    await state.update_data(address=address)
    data = await state.get_data()
    await message.answer(
        build_summary(data),
        reply_markup=confirmation_keyboard()
    )
    await state.set_state(OrderForm.waiting_confirmation)


@dp.message(OrderForm.waiting_confirmation, F.text == "✏️ Ўзгартириш")
async def edit_handler(message: Message, state: FSMContext):
    await state.set_state(OrderForm.waiting_order_id)
    await message.answer(
        "🔄 <b>Маълумотларни қайта киритиш бошланди.</b>\n\n"
        "Илтимос, <b>буюртма ID рақамини қайта киритинг.</b>\n\n"
        "📌 <b>Намуна:</b>\n"
        "<code>0012345</code>",
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(OrderForm.waiting_confirmation, F.text == "✅ Тасдиқлаш")
async def confirm_handler(message: Message, state: FSMContext):
    data = await state.get_data()

    request_id = str(int(time.time() * 1000))
    PENDING_REQUESTS[request_id] = {
        "status": "pending",
        "user_id": message.from_user.id,
        "username": message.from_user.username,
        "order_id": data["order_id"],
        "fullname": data["fullname"],
        "country": data["country"],
        "city": data["city"],
        "address": data["address"],
    }

    admin_text = build_admin_text(data, message)

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                admin_text,
                reply_markup=admin_inline_keyboard(request_id)
            )
        except Exception as e:
            print(f"Adminга юборишда хато: {e}")

    await message.answer(
        "✅ <b>Раҳмат!</b>\n\n"
        "Сизнинг маълумотларингиз қабул қилинди ва\n"
        "👨‍💼 <b>администраторларга юборилди.</b>\n\n"
        "📩 Текширувдан кейин сизга хабар берилади.",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()


@dp.message(OrderForm.waiting_confirmation)
async def wrong_confirmation_handler(message: Message):
    await message.answer("⚠️ Илтимос, <b>✅ Тасдиқлаш</b> ёки <b>✏️ Ўзгартириш</b> тугмасини босинг.")


@dp.callback_query(F.data.startswith("approve:"))
async def approve_order(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Сиз админ эмассиз.", show_alert=True)
        return

    request_id = callback.data.split(":")[1]
    request_data = PENDING_REQUESTS.get(request_id)

    if not request_data:
        await callback.answer("Буюртма топилмади.", show_alert=True)
        return

    if request_data["status"] != "pending":
        await callback.answer("Бу буюртма аллақачон кўриб чиқилган.", show_alert=True)
        return

    request_data["status"] = "approved"

    new_text = callback.message.text + "\n\n✅ <b>Ҳолат:</b> ТАСДИҚЛАНДИ"
    await callback.message.edit_text(new_text)

    try:
        await bot.send_message(
            request_data["user_id"],
            "🎉 <b>Ассалому алайкум!</b>\n\n"
            "Сиз юборган <b>етказиб бериш маълумотлари тасдиқланди.</b>\n\n"
            "📦 Буюртмангиз тез орада етказиб берилади."
        )
    except Exception as e:
        print(f"Фойдаланувчига хабар юборишда хато: {e}")

    await callback.answer("Буюртма тасдиқланди.")


@dp.callback_query(F.data.startswith("reject:"))
async def reject_order(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Сиз админ эмассиз.", show_alert=True)
        return

    request_id = callback.data.split(":")[1]
    request_data = PENDING_REQUESTS.get(request_id)

    if not request_data:
        await callback.answer("Буюртма топилмади.", show_alert=True)
        return

    if request_data["status"] != "pending":
        await callback.answer("Бу буюртма аллақачон кўриб чиқилган.", show_alert=True)
        return

    request_data["status"] = "rejected"

    new_text = callback.message.text + "\n\n❌ <b>Ҳолат:</b> БЕКОР ҚИЛИНДИ"
    await callback.message.edit_text(new_text)

    try:
        await bot.send_message(
            request_data["user_id"],
            "⚠️ <b>Ассалому алайкум.</b>\n\n"
            "Сиз юборган маълумотлар\n"
            "<b>администратор томонидан бекор қилинди.</b>\n\n"
            "📌 Илтимос, маълумотларни текшириб қайта юборинг."
        )
    except Exception as e:
        print(f"Фойдаланувчига хабар юборишда хато: {e}")

    await callback.answer("Буюртма бекор қилинди.")


async def main():
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
