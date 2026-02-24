import asyncio
import logging
import aiohttp
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import API_TOKEN, CRYPTOBOT_TOKEN, ADMIN_ID, RENT_PRICE, COUNTRIES, INVOICE_COOLDOWN, PHYS_ACCOUNTS, NUMBERS_PER_PAGE
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

def get_country_menu():
    kb = []
    for key, data in COUNTRIES.items():
        kb.append([InlineKeyboardButton(
            text=f"{data['flag']} {data['name']} ({data['code']})",
            callback_data=f"country_{key}"
        )])
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
    flags = ' '.join([d['flag'] for d in COUNTRIES.values()])
    await message.answer(
        f"👋 <b>Привет! Это GOGOGO.</b>\n\n"
        f"📱 <b>Аренда номеров:</b> от {RENT_PRICE}$\n"
        f"🌍 <b>Страны:</b> {flags}\n"
        f"🛒 <b>Физ аккаунты:</b> в наличии\n\n"
        f"Выберите раздел:",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        f"🔧 <b>Админ-панель</b>\n\n"
        f"Текущая цена: <b>{RENT_PRICE}$</b>",
        reply_markup=get_admin_menu(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "admin_set_price")
async def admin_set_price(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    await callback.message.answer(
        "💰 <b>Введите новую цену (в $):</b>\n\n"
        f"Текущая: {RENT_PRICE}$\nПример: 2.0",
        parse_mode="HTML"
    )
    await state.set_state(AdminState.setting_price)
    await callback.answer()

@dp.message(AdminState.setting_price)
async def process_new_price(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        new_price = float(message.text.replace(',', '.'))
        if new_price <= 0:
            raise ValueError
        global RENT_PRICE
        RENT_PRICE = new_price
        await message.answer(f"✅ <b>Цена изменена!</b>\n\nНовая цена: <b>{RENT_PRICE}$</b>", parse_mode="HTML")
        await state.clear()
    except:
        await message.answer("❌ <b>Ошибка!</b>\n\nВведите корректное число (например: 1.5 или 2.0)", parse_mode="HTML")

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    await callback.message.answer("📊 <b>Статистика</b>\n\nВ разработке...", parse_mode="HTML")
    await callback.answer()

# --- АРЕНДА НОМЕРОВ ---
@dp.callback_query(F.data == "menu_rent")
async def open_rent_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🌍 <b>Выберите страну:</b>", reply_markup=get_country_menu(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("country_"))
async def country_selected(callback: types.CallbackQuery, state: FSMContext):
    country_key = callback.data.replace("country_", "")
    country_data = COUNTRIES[country_key]
    numbers = db.get_available_numbers(country_key, limit=NUMBERS_PER_PAGE)
    
    if not numbers:
        await callback.answer("❌ Нет свободных номеров", show_alert=True)
        return
    
    await state.update_data(country_key=country_key, numbers=numbers)
    
    await callback.message.edit_text(
        f"{country_data['flag']} <b>Номера ({country_data['name']})</b>\n\n"
        f"💰 {RENT_PRICE}$ / 30 мин\n"
        f"📄 Доступно: {len(numbers)}",
        reply_markup=get_number_keyboard(numbers, country_key),
        parse_mode="HTML"
    )

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
        "🛒 <b>Магазин аккаунтов</b>\n\nВыберите тип:",
        reply_markup=get_phys_catalog(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("phys_") & ~F.data.startswith("phys_qty") & ~F.data.startswith("phys_confirm"))
async def select_phys_account(callback: types.CallbackQuery, state: FSMContext):
    account_type = callback.data.replace("phys_", "")
    if account_type not in PHYS_ACCOUNTS:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return
    
    data = PHYS_ACCOUNTS[account_type]
    await state.update_data(account_type=account_type)
    
    await callback.message.edit_text(
        f"{data['name']}\n\n"
        f"💰 <b>Цена:</b> {data['price']}$\n"
        f"📝 <b>Описание:</b> {data['description']}\n\n"
        f"Выберите количество:",
        reply_markup=get_phys_quantity_keyboard(account_type),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("phys_qty_"))
async def phys_quantity_selected(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split('_')
    # формат: phys_qty_{account_type}_{qty}
    account_type = parts[2]
    qty = int(parts[3])

    account_info = PHYS_ACCOUNTS.get(account_type)
    if not account_info:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return

    # расчёт цены
    price_per_unit = account_info['price']
    if account_info.get('bulk_price') and qty >= account_info.get('bulk_min', float('inf')):
        price_per_unit = account_info['bulk_price']
    total_price = round(price_per_unit * qty, 2)

    # проверка кулдауна
    if not db.check_cooldown(callback.from_user.id, INVOICE_COOLDOWN):
        await callback.answer("⏳ Подождите 60 секунд!", show_alert=True)
        return

    # создаём счёт через CryptoBot
    invoice_result = await create_invoice(total_price, f"{account_info['name']} x{qty}")
    if not invoice_result.get('ok'):
        await callback.answer("❌ Ошибка создания счета", show_alert=True)
        return

    invoice_data = invoice_result['result']
    invoice_id = invoice_data['invoice_id']
    invoice_url = invoice_data['pay_url']

    # сохраняем данные в состоянии
    await state.update_data(
        phys_invoice_id=invoice_id,
        phys_account_type=account_type,
        phys_quantity=qty,
        phys_total_price=total_price,
        phys_price_per_unit=price_per_unit
    )
    await state.set_state(PhysState.waiting_payment)

    # отправляем сообщение с оплатой
    await callback.message.edit_text(
        f"💳 <b>Счет создан!</b>\n\n"
        f"Товар: {account_info['name']}\n"
        f"Количество: {qty}\n"
        f"Сумма: {total_price}$\n\n"
        f"После оплаты нажмите кнопку ниже.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=invoice_url)],
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data="phys_confirm_pay")]
        ]),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "phys_confirm_pay")
async def confirm_phys_payment(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    invoice_id = data.get('phys_invoice_id')
    if not invoice_id:
        await callback.answer("❌ Сначала создайте счет", show_alert=True)
        return

    status_result = await check_invoice_status(invoice_id)
    if not (status_result.get('ok') and status_result['result'].get('status') == 'paid'):
        await callback.answer("⏳ Платёж не найден или ещё не оплачен", show_alert=True)
        return

    # платёж подтверждён
    account_type = data['phys_account_type']
    quantity = data['phys_quantity']
    price_per_unit = data['phys_price_per_unit']
    user_id = callback.from_user.id

    # генерируем и сохраняем аккаунты
    account_ids = db.generate_and_save_phys_accounts(
        account_type, quantity, user_id, price_per_unit
    )

    # получаем данные аккаунтов для выдачи
    accounts_data = db.get_phys_accounts_by_ids(account_ids)

    # формируем сообщение с аккаунтами
    text = f"✅ <b>Оплачено!</b>\n\nВаши аккаунты:\n"
    for acc in accounts_data:
        text += f"\n📞 <code>{acc['phone']}</code>\n"
        text += f"👤 {acc['username']} | {acc['password']}\n"
        if acc.get('extra'):
            text += f"📦 {acc['extra']}\n"
        text += "—\n"

    await callback.message.edit_text(text, parse_mode="HTML")
    await state.clear()

# --- ОБЩИЕ ---
@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("👋 <b>Главное меню</b>", reply_markup=get_main_menu(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "menu_purchases")
async def show_purchases(callback: types.CallbackQuery):
    # Здесь можно реализовать показ истории покупок
    await callback.answer("📦 Раздел в разработке", show_alert=True)

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
