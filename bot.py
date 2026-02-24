import asyncio
import logging
import aiohttp
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import API_TOKEN, CRYPTOBOT_TOKEN, ADMIN_ID, RENT_PRICE, COUNTRIES, INVOICE_COOLDOWN
import database as db

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# ================= СОСТОЯНИЯ =================
class RentState(StatesGroup):
    choosing_country = State()
    waiting_payment = State()
    active_rent = State()

class AdminState(StatesGroup):
    setting_price = State()

# ================= КЛАВИАТУРЫ =================
def get_main_menu():
    kb = [
        [InlineKeyboardButton(text="📱 Аренда номеров", callback_data="menu_rent")],
        [InlineKeyboardButton(text="🛒 Мои покупки", callback_data="menu_purchases")],
        [InlineKeyboardButton(text="👤 Физ аккаунты", callback_data="menu_phys"),
         InlineKeyboardButton(text="🔨 Сносер", callback_data="menu_snoser")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_country_menu():
    kb = []
    for key, data in COUNTRIES.items():
        kb.append([InlineKeyboardButton(text=f"{data['flag']} {data['name']} ({data['code']})", callback_data=f"country_{key}")])
    kb.append([InlineKeyboardButton(text="🔙 В меню", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_number_keyboard(numbers, country_key):
    kb = []
    flag = COUNTRIES[country_key]['flag']
    for num in numbers:
        cb_data = f"num_{num['id']}_{country_key}"
        kb.append([InlineKeyboardButton(text=f"{flag} {num['masked']}", callback_data=cb_data)])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_pay_keyboard(number_id, country_key):
    kb = [
        [InlineKeyboardButton(text=f"💳 Оплатить {RENT_PRICE}$", callback_data=f"pay_{number_id}_{country_key}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_check_keyboard(number_id, country_key):
    kb = [
        [InlineKeyboardButton(text="🔔 Проверить СМС", callback_data=f"check_{number_id}_{country_key}")],
        [InlineKeyboardButton(text="📋 Копировать", callback_data=f"copy_{number_id}_{country_key}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_purchases_keyboard(purchases):
    kb = []
    for i, p in enumerate(purchases[:5]):
        kb.append([InlineKeyboardButton(text=f"📞 {p['full']}", callback_data=f"purchase_{i}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_admin_menu():
    kb = [
        [InlineKeyboardButton(text="💰 Изменить цену", callback_data="admin_set_price")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ================= CRYPTO PAY =================
async def create_invoice(amount, description):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN, "Content-Type": "application/json"}
    data = {"asset": "USDT", "amount": str(amount), "description": description, "expires_in": 3600}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, headers=headers) as response:
            return await response.json()

async def check_invoice_status(invoice_id):
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN, "Content-Type": "application/json"}
    params = {"invoice_ids": [invoice_id]}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=params, headers=headers) as response:
            result = await response.json()
            if result.get('ok') and result.get('result', {}).get('items'):
                for inv in result['result']['items']:
                    if str(inv['invoice_id']) == str(invoice_id):
                        return {'ok': True, 'result': {'status': inv['status']}}
            return {'ok': False, 'result': {'status': 'not_found'}}

# ================= ХЕНДЛЕРЫ =================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"👋 <b>Привет! Это GOGOGO — аренда номеров.</b>\n\n"
        f"🌍 <b>Страны:</b> {', '.join([d['flag'] for d in COUNTRIES.values()])}\n"
        f"💰 <b>Цена:</b> {RENT_PRICE}$ / 30 минут\n\n"
        f"Выберите раздел:",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "menu_rent")
async def open_rent_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🌍 <b>Выберите страну:</b>", reply_markup=get_country_menu(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("country_"))
async def country_selected(callback: types.CallbackQuery, state: FSMContext):
    country_key = callback.data.replace("country_", "")
    numbers = db.get_available_numbers(country_key, limit=5)
    
    if not numbers:
        await callback.answer("❌ Нет свободных номеров", show_alert=True)
        return
    
    flag = COUNTRIES[country_key]['flag']
    name = COUNTRIES[country_key]['name']
    
    await callback.message.edit_text(
        f"{flag} <b>Номера ({name})</b>\n\n"
        f"💰 {RENT_PRICE}$ / 30 мин\n"
        f"📄 Доступно: {len(numbers)}\n\n"
        f"<i>Нажмите на номер:</i>",
        reply_markup=get_number_keyboard(numbers, country_key),
        parse_mode="HTML"
    )
    await state.update_data(country_key=country_key, numbers=numbers)

@dp.callback_query(F.data.startswith("num_"))
async def number_selected(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split('_')
    number_id = int(parts[1])
    country_key = parts[2]
    
    data = await state.get_data()
    numbers = data.get('numbers', [])
    selected = next((n for n in numbers if n['id'] == number_id), None)
    
    if not selected:
        await callback.answer("❌ Номер не найден", show_alert=True)
        return
    
    flag = COUNTRIES[country_key]['flag']
    await callback.message.edit_text(
        f"{flag} <b>Выбран:</b> {selected['masked']}\n\n"
        f"💰 {RENT_PRICE}$\n⏱ 30 минут",
        reply_markup=get_pay_keyboard(number_id, country_key),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("pay_"))
async def pay_number(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    # 🔒 АНТИ-СПАМ
    if not db.check_cooldown(user_id, INVOICE_COOLDOWN):
        await callback.answer("⏳ Подождите 60 секунд перед следующим запросом!", show_alert=True)
        return
    
    parts = callback.data.split('_')
    number_id = int(parts[1])
    country_key = parts[2]
    
    data = await state.get_data()
    numbers = data.get('numbers', [])
    selected = next((n for n in numbers if n['id'] == number_id), None)
    
    if not selected:
        await callback.answer("❌ Номер не найден", show_alert=True)
        return
    
    invoice_result = await create_invoice(RENT_PRICE, f"Аренда {selected['masked']}")
    
    if invoice_result.get('ok'):
        invoice_data = invoice_result['result']
        invoice_id = invoice_data['invoice_id']
        invoice_url = invoice_data['pay_url']
        
        await state.update_data(invoice_id=invoice_id, number_id=number_id, country_key=country_key, selected=selected)
        await state.set_state(RentState.waiting_payment)
        
        await callback.message.edit_text(
            f"💳 <b>Счет создан!</b>\n\n"
            f"💰 {RENT_PRICE}$\n"
            f"📞 {selected['masked']}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", url=invoice_url)],
                [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"check_pay_{number_id}_{country_key}")]
            ]),
            parse_mode="HTML"
        )
    else:
        await callback.answer("❌ Ошибка создания счета", show_alert=True)

@dp.callback_query(F.data.startswith("check_pay_"))
async def check_payment(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split('_')
    number_id = int(parts[2])
    country_key = parts[3]
    
    data = await state.get_data()
    invoice_id = data.get('invoice_id')
    selected = data.get('selected')
    
    if not invoice_id:
        await callback.answer("❌ Сначала создайте счет", show_alert=True)
        return
    
    status_result = await check_invoice_status(invoice_id)
    
    if status_result.get('ok') and status_result['result'].get('status') == 'paid':
        db.rent_number(number_id, callback.from_user.id)
        
        await state.set_state(RentState.active_rent)
        await callback.message.edit_text(
            f"✅ <b>Оплачено!</b>\n\n"
            f"📞 <code>{selected['full']}</code>\n\n"
            f"⏱ 30 минут",
            reply_markup=get_check_keyboard(number_id, country_key),
            parse_mode="HTML"
        )
    else:
        await callback.answer("⏳ Ждём оплату...", show_alert=True)

@dp.callback_query(F.data == "menu_purchases")
async def show_purchases(callback: types.CallbackQuery):
    purchases = db.get_user_purchases(callback.from_user.id)
    
    if not purchases:
        await callback.answer("🛒 У вас пока нет покупок", show_alert=True)
        return
    
    text = "🛒 <b>Ваши покупки:</b>\n\n"
    for p in purchases[:5]:
        text += f"📞 {p['full']} | {p['price']}$ | {p['expired']}\n"
    
    await callback.message.answer(text, reply_markup=get_purchases_keyboard(purchases), parse_mode="HTML")

@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("👋 <b>Главное меню</b>", reply_markup=get_main_menu(), parse_mode="HTML")

@dp.callback_query(F.data == "menu_phys")
async def phys_accounts(callback: types.CallbackQuery):
    await callback.answer("🚧 Скоро будет...", show_alert=True)

@dp.callback_query(F.data == "menu_snoser")
async def snoser(callback: types.CallbackQuery):
    await callback.answer("🚧 Скоро будет...", show_alert=True)

@dp.callback_query(F.data.startswith("check_"))
async def check_sms(callback: types.CallbackQuery):
    temp = await callback.message.answer("🔔 <i>Нет новых СМС...</i>", parse_mode="HTML")
    await asyncio.sleep(5)
    try:
        await temp.delete()
    except:
        pass

@dp.callback_query(F.data.startswith("copy_"))
async def copy_number(callback: types.CallbackQuery):
    await callback.answer("📋 Скопировано!", show_alert=True)

# ================= ЗАПУСК =================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
