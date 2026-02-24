import asyncio
import logging
import aiohttp
import json
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import API_TOKEN, CRYPTOBOT_TOKEN, ADMIN_ID, RENT_PRICE, COUNTRIES, INVOICE_COOLDOWN, PHYS_ACCOUNTS
import database as db

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# ================= СОСТОЯНИЯ =================
class RentState(StatesGroup):
    choosing_country = State()
    waiting_payment = State()
    active_rent = State()

class PhysState(StatesGroup):
    selecting_account = State()
    selecting_quantity = State()
    waiting_payment = State()

class AdminState(StatesGroup):
    setting_price = State()

# ================= КЛАВИАТУРЫ =================
def get_main_menu():
    kb = [
        [InlineKeyboardButton(text="📱 Аренда номеров", callback_data="menu_rent")],
        [InlineKeyboardButton(text="🛒 Физ аккаунты", callback_data="menu_phys")],
        [InlineKeyboardButton(text="📦 Мои покупки", callback_data="menu_purchases")],
        [InlineKeyboardButton(text="🔨 Сносер", callback_data="menu_snoser")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_phys_catalog():
    kb = []
    for key, data in PHYS_ACCOUNTS.items():
        price_text = f"{data['price']}$"
        if data.get('bulk_price'):
            price_text += f" • от {data['bulk_min']}шт: {data['bulk_price']}$"
        kb.append([InlineKeyboardButton(text=f"{data['name']} — {price_text}", callback_data=f"phys_{key}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_phys_quantity_keyboard(account_type):
    kb = [
        [InlineKeyboardButton(text="1 шт", callback_data=f"phys_qty_{account_type}_1")],
        [InlineKeyboardButton(text="5 шт", callback_data=f"phys_qty_{account_type}_5")],
        [InlineKeyboardButton(text="10 шт (скидка)", callback_data=f"phys_qty_{account_type}_10")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_phys")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_phys_pay_keyboard(account_type, quantity, price):
    kb = [
        [InlineKeyboardButton(text=f"💳 Оплатить {price}$", callback_data=f"phys_pay_{account_type}_{quantity}_{price}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_phys")]
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
        f"👋 <b>Привет! Это GOGOGO.</b>\n\n"
        f"📱 <b>Аренда номеров:</b> от {RENT_PRICE}$\n"
        f"🛒 <b>Физ аккаунты:</b> в наличии\n\n"
        f"Выберите раздел:",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )

# --- АРЕНДА НОМЕРОВ ---
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
        f"📄 Доступно: {len(numbers)}",
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
    if not db.check_cooldown(user_id, INVOICE_COOLDOWN):
        await callback.answer("⏳ Подождите 60 секунд!", show_alert=True)
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

# --- ФИЗ АККАУНТЫ ---
@dp.callback_query(F.data == "menu_phys")
async def open_phys_menu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🛒 <b>Магазин аккаунтов</b>\n\n"
        "Выберите тип аккаунта:",
        reply_markup=get_phys_catalog(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("phys_") and not F.data.startswith("phys_qty") and not F.data.startswith("phys_pay"))
async def select_phys_account(callback: types.CallbackQuery, state: FSMContext):
    account_type = callback.data.replace("phys_", "")
    
    if account_type not in PHYS_ACCOUNTS:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return
    
    data = PHYS_ACCOUNTS[account_type]
    
    # Проверяем наличие
    available = db.get_available_phys_accounts(account_type, quantity=1)
    if not available:
        await callback.answer("❌ Товар закончился", show_alert=True)
        return
    
    await state.update_data(account_type=account_type)
    await state.set_state(PhysState.selecting_quantity)
    
    await callback.message.edit_text(
        f"{data['name']}\n\n"
        f"💰 <b>Цена:</b> {data['price']}$\n"
        f"📦 <b>Опт:</b> {data['bulk_price']}$ от {data['bulk_min']}шт\n" if data.get('bulk_price') else ""
        f"📝 <b>Описание:</b> {data['description']}\n\n"
        f"Выберите количество:",
        reply_markup=get_phys_quantity_keyboard(account_type),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("phys_qty_"))
async def select_quantity(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split('_')
    account_type = parts[2]
    quantity = int(parts[3])
    
    data = PHYS_ACCOUNTS[account_type]
    
    # Считаем цену с учётом скидки
    if quantity >= data.get('bulk_min', 999) and data.get('bulk_price'):
        price = data['bulk_price'] * quantity
        discount = True
    else:
        price = data['price'] * quantity
        discount = False
    
    # Проверяем наличие нужного количества
    available = db.get_available_phys_accounts(account_type, quantity=quantity)
    if len(available) < quantity:
        await callback.answer(f"❌ Доступно только {len(available)} шт", show_alert=True)
        return
    
    await state.update_data(quantity=quantity, price=price, discount=discount)
    await state.set_state(PhysState.waiting_payment)
    
    discount_text = "🎁 <b>Скидка применена!</b>\n" if discount else ""
    
    await callback.message.edit_text(
        f"🛒 <b>Заказ:</b>\n\n"
        f"📦 Товар: {data['name']}\n"
        f"🔢 Количество: {quantity} шт\n"
        f"💰 <b>Итого:</b> {price}$\n\n"
        f"{discount_text}"
        f"Нажмите для оплаты:",
        reply_markup=get_phys_pay_keyboard(account_type, quantity, price),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("phys_pay_"))
async def pay_phys_account(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if not db.check_cooldown(user_id, INVOICE_COOLDOWN):
        await callback.answer("⏳ Подождите 60 секунд!", show_alert=True)
        return
    
    parts = callback.data.split('_')
    account_type = parts[2]
    quantity = int(parts[3])
    price = float(parts[4])
    
    data = PHYS_ACCOUNTS[account_type]
    
    invoice_result = await create_invoice(price, f"Физ аккаунты {data['name']} x{quantity}")
    
    if invoice_result.get('ok'):
        invoice_data = invoice_result['result']
        invoice_id = invoice_data['invoice_id']
        invoice_url = invoice_data['pay_url']
        
        await state.update_data(invoice_id=invoice_id, account_type=account_type, quantity=quantity, price=price)
        
        await callback.message.edit_text(
            f"💳 <b>Счет создан!</b>\n\n"
            f"📦 {data['name']} x{quantity}\n"
            f"💰 {price}$",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", url=invoice_url)],
                [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"phys_check_{account_type}_{quantity}_{price}")]
            ]),
            parse_mode="HTML"
        )
    else:
        await callback.answer("❌ Ошибка создания счета", show_alert=True)

@dp.callback_query(F.data.startswith("phys_check_"))
async def check_phys_payment(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split('_')
    account_type = parts[2]
    quantity = int(parts[3])
    price = float(parts[4])
    
    data = await state.get_data()
    invoice_id = data.get('invoice_id')
    
    if not invoice_id:
        await callback.answer("❌ Сначала создайте счет", show_alert=True)
        return
    
    status_result = await check_invoice_status(invoice_id)
    
    if status_result.get('ok') and status_result['result'].get('status') == 'paid':
        # Выдаём аккаунты
        accounts = db.get_available_phys_accounts(account_type, quantity=quantity)
        
        if len(accounts) < quantity:
            await callback.answer("❌ Товар закончился пока вы оплачивали", show_alert=True)
            return
        
        # Помечаем как проданные
        for acc in accounts:
            db.sell_phys_account(acc['id'], callback.from_user.id, price/quantity)
        
        # Формируем выдачу
        delivery_text = f"✅ <b>Оплата подтверждена!</b>\n\n"
        delivery_text += f"📦 <b>Товар:</b> {PHYS_ACCOUNTS[account_type]['name']}\n"
        delivery_text += f"🔢 <b>Количество:</b> {quantity} шт\n\n"
        
        for i, acc in enumerate(accounts, 1):
            delivery_text += f"━━━━━━━━━━━━━━━━\n"
            delivery_text += f"📋 <b>Аккаунт #{i}</b>\n"
            delivery_text += f"📱 Телефон: <code>{acc['phone']}</code>\n"
            
            if acc.get('session') and acc['session']:
                delivery_text += f"🔑 Session: <code>{acc['session'][:50]}...</code>\n"
            if acc.get('username') and acc['username']:
                delivery_text += f"👤 Username: <code>{acc['username']}</code>\n"
            if acc.get('password') and acc['password']:
                delivery_text += f"🔒 Пароль: <code>{acc['password']}</code>\n"
            
            # Доп данные
            try:
                extra = json.loads(acc['extra_data']) if acc['extra_data'] else {}
                if extra.get('registered'):
                    delivery_text += f"📅 Регистрация: {extra['registered']}\n"
                if extra.get('aged_years'):
                    delivery_text += f"🕰 Отлежка: {extra['aged_years']} лет\n"
                if extra.get('code'):
                    delivery_text += f"🎫 Код: <code>{extra['code']}</code>\n"
            except:
                pass
            
            delivery_text += f"━━━━━━━━━━━━━━━━\n\n"
        
        delivery_text += f"<i>💡 Сохраните данные в избранное!</i>"
        
        await callback.message.answer(delivery_text, parse_mode="HTML")
        
        await callback.message.edit_text(
            "✅ <b>Заказ выдан!</b>\n\n"
            "Данные отправлены выше 👆\n\n"
            "Сохраните в избранное!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🛒 Ещё покупки", callback_data="menu_phys")],
                [InlineKeyboardButton(text="🔙 В меню", callback_data="back_main")]
            ]),
            parse_mode="HTML"
        )
        
        await state.clear()
    else:
        await callback.answer("⏳ Ждём оплату...", show_alert=True)

# --- МОИ ПОКУПКИ ---
@dp.callback_query(F.data == "menu_purchases")
async def show_purchases(callback: types.CallbackQuery):
    rentals = db.get_user_purchases(callback.from_user.id)
    phys = db.get_user_phys_purchases(callback.from_user.id)
    
    if not rentals and not phys:
        await callback.answer("🛒 У вас пока нет покупок", show_alert=True)
        return
    
    text = "📦 <b>Ваши покупки:</b>\n\n"
    
    if rentals:
        text += "📱 <b>Аренда номеров:</b>\n"
        for r in rentals[:3]:
            text += f"  {r['full']} | {r['price']}$ | {r['expired']}\n"
        text += "\n"
    
    if phys:
        text += "🛒 <b>Физ аккаунты:</b>\n"
        for p in phys[:3]:
            text += f"  {p['type']} | {p['phone']} | {p['price']}$\n"
    
    await callback.message.answer(text, parse_mode="HTML")

# --- ОБЩЕЕ ---
@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("👋 <b>Главное меню</b>", reply_markup=get_main_menu(), parse_mode="HTML")

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
