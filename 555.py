import asyncio
import logging
import random
import aiohttp
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ================= НАСТРОЙКИ =================
API_TOKEN = '8500113818:AAEIG8aABNiwbCXLq08KzxJ1fkv1PhJtnqQ'
CRYPTOBOT_TOKEN = '528164:AAfmR2y2vzP5sM0Miv5HHW48oyEW3DVB3Er'  # из https://t.me/CryptoBot → Настройки → API
RENT_PRICE = 0.1
ADMIN_ID = 8000395560  # Твой Telegram ID (узнай у @userinfobot)
NUMBERS_PER_PAGE = 5

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# ================= ХРАНИЛИЩЕ =================
user_rentals = {}

# ================= СОСТОЯНИЯ =================
class RentState(StatesGroup):
    choosing_country = State()
    waiting_payment = State()
    active_rent = State()

class AdminState(StatesGroup):
    setting_price = State()

# ================= ГЕНЕРАЦИЯ НОМЕРОВ =================
def generate_phone_number(country_code):
    if country_code == "+7":
        digits = ''.join([str(random.randint(0, 9)) for _ in range(10)])
        full_number = f"+7{digits}"
        masked = f"+7{digits[:3]}*{digits[-5:]}*"
    elif country_code == "+1":
        digits = ''.join([str(random.randint(0, 9)) for _ in range(10)])
        full_number = f"+1{digits}"
        masked = f"+1{digits[:3]}*{digits[-5:]}*"
    else:
        return None, None
    return full_number, masked

def generate_number_pool(country_code, count=15):
    pool = []
    for i in range(count):
        full, masked = generate_phone_number(country_code)
        pool.append({'id': i, 'full': full, 'masked': masked, 'country': country_code})
    return pool

# ================= КЛАВИАТУРЫ =================
def get_main_menu():
    kb = [
        [InlineKeyboardButton(text="📱 Аренда номеров", callback_data="menu_rent")],
        [InlineKeyboardButton(text="👤 Физ аккаунты", callback_data="menu_phys"),
         InlineKeyboardButton(text="🔨 Сносер", callback_data="menu_snoser")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_country_menu():
    kb = [
        [InlineKeyboardButton(text="🇷🇺 Россия (+7)", callback_data="country_russia")],
        [InlineKeyboardButton(text="🇺🇸 Америка (+1)", callback_data="country_usa")],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_number_page_keyboard(numbers, country_code, page=0, total_pages=1):
    kb = []
    flag = "🇷🇺" if country_code == "+7" else "🇺🇸"
    
    for num in numbers:
        cb_data = f"num_{num['id']}_{country_code.replace('+', '')}"
        kb.append([InlineKeyboardButton(text=f"{flag} {num['masked']}", callback_data=cb_data)])
    
    page_nav = []
    if page > 0:
        page_nav.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"page_{country_code.replace('+', '')}_{page-1}"))
    if page < total_pages - 1:
        page_nav.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"page_{country_code.replace('+', '')}_{page+1}"))
    if page_nav:
        kb.append(page_nav)
    
    kb.append([InlineKeyboardButton(text="🔙 В меню", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_pay_keyboard(number_id, country_code):
    kb = [
        [InlineKeyboardButton(text=f"💳 Оплатить {RENT_PRICE}$", callback_data=f"pay_{number_id}_{country_code}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_check_notification_keyboard(number_id, country_code):
    kb = [
        [InlineKeyboardButton(text="🔔 Проверить уведомления", callback_data=f"check_{number_id}_{country_code}")],
        [InlineKeyboardButton(text="📞 Мой номер", callback_data=f"my_number_{number_id}_{country_code}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_admin_menu():
    kb = [
        [InlineKeyboardButton(text="💰 Изменить цену", callback_data="admin_set_price")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ================= CRYPTO PAY API =================
async def create_invoice(amount, description):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {
        "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN,
        "Content-Type": "application/json"
    }
    data = {
        "asset": "USDT",
        "amount": str(amount),
        "description": description,
        "expires_in": 3600,
        "allow_comments": False,
        "allow_anonymous": False
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, headers=headers) as response:
            result = await response.json()
            print(f"🔍 CreateInvoice: {result}")
            return result

async def check_invoice_status(invoice_id):
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {
        "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN,
        "Content-Type": "application/json"
    }
    params = {"invoice_ids": [invoice_id]}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=params, headers=headers) as response:
            result = await response.json()
            print(f"🔍 GetInvoices: {result}")
            if result.get('ok') and result.get('result', {}).get('items'):
                for inv in result['result']['items']:
                    if str(inv['invoice_id']) == str(invoice_id):
                        return {'ok': True, 'result': {'status': inv['status']}}
            return {'ok': False, 'result': {'status': 'not_found'}}

# ================= ХЕНДЛЕРЫ =================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"👋 <b>Привет! Это сервис аренды номеров.</b>\n\n"
        f" <b>Доступные страны:</b>\n"
        f"  • 🇷🇺 Россия (+7)\n"
        f"  • 🇺 Америка (+1)\n\n"
        f"💰 <b>Цена:</b> {RENT_PRICE}$ / 30 минут\n\n"
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
        f"Текущая: {RENT_PRICE}$\n"
        f"Пример: 2.0",
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
        
        await message.answer(
            f"✅ <b>Цена изменена!</b>\n\n"
            f"Новая цена: <b>{RENT_PRICE}$</b>",
            parse_mode="HTML"
        )
        await state.clear()
    except:
        await message.answer(
            "❌ <b>Ошибка!</b>\n\n"
            "Введите корректное число (например: 1.5 или 2.0)",
            parse_mode="HTML"
        )

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    total_rentals = len(user_rentals)
    paid_rentals = sum(1 for r in user_rentals.values() if r.get('paid'))
    
    await callback.message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"Всего аренд: {total_rentals}\n"
        f"Оплачено: {paid_rentals}\n"
        f"Ожидает: {total_rentals - paid_rentals}",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "menu_rent")
async def open_rent_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🌍 <b>Выберите страну для аренды:</b>",
        reply_markup=get_country_menu(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("country_"))
async def country_selected(callback: types.CallbackQuery, state: FSMContext):
    country_code = "+7" if "russia" in callback.data else "+1"
    country_name = "Россия" if "russia" in callback.data else "Америка"
    flag = "🇷🇺" if "russia" in callback.data else "🇺🇸"
    
    numbers = generate_number_pool(country_code, count=15)
    total_pages = (len(numbers) + NUMBERS_PER_PAGE - 1) // NUMBERS_PER_PAGE
    
    await state.update_data(
        numbers=numbers,
        country_code=country_code,
        country_name=country_name,
        total_pages=total_pages,
        current_page=0
    )
    
    page_numbers = numbers[0:NUMBERS_PER_PAGE]
    await callback.message.edit_text(
        f"{flag} <b>Доступные номера ({country_name})</b>\n\n"
        f"💰 Цена: <b>{RENT_PRICE}$</b> / 30 мин\n"
        f"📄 Страница 1 из {total_pages}\n\n"
        f"<i>Нажмите на номер для аренды:</i>",
        reply_markup=get_number_page_keyboard(page_numbers, country_code, 0, total_pages),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("page_"))
async def change_page(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split('_')
    country_code = f"+{parts[1]}"
    new_page = int(parts[2])
    
    data = await state.get_data()
    numbers = data.get('numbers', [])
    total_pages = data.get('total_pages', 1)
    country_name = data.get('country_name', '')
    flag = "🇷🇺" if country_code == "+7" else "🇺🇸"
    
    page_numbers = numbers[new_page*NUMBERS_PER_PAGE : (new_page+1)*NUMBERS_PER_PAGE]
    await state.update_data(current_page=new_page)
    
    await callback.message.edit_text(
        f"{flag} <b>Доступные номера ({country_name})</b>\n\n"
        f"💰 Цена: <b>{RENT_PRICE}$</b> / 30 мин\n"
        f"📄 Страница {new_page+1} из {total_pages}\n\n"
        f"<i>Нажмите на номер для аренды:</i>",
        reply_markup=get_number_page_keyboard(page_numbers, country_code, new_page, total_pages),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("num_"))
async def number_selected(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split('_')
    number_id = int(parts[1])
    country_code = f"+{parts[2]}"
    flag = "🇷🇺" if country_code == "+7" else "🇺🇸"
    
    data = await state.get_data()
    numbers = data.get('numbers', [])
    selected = next((n for n in numbers if n['id'] == number_id), None)
    
    if not selected:
        await callback.answer("❌ Номер не найден", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"{flag} <b>Вы выбрали:</b> {selected['masked']}\n\n"
        f"🌍 Страна: {'Россия' if country_code == '+7' else 'Америка'}\n"
        f"⏱ Аренда: 30 минут\n"
        f"💰 Цена: {RENT_PRICE}$\n\n"
        f"<i>После оплаты номер будет раскрыт.</i>",
        reply_markup=get_pay_keyboard(number_id, country_code.replace('+', '')),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("pay_"))
async def pay_number(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split('_')
    number_id = int(parts[1])
    country_code = f"+{parts[2]}"
    
    data = await state.get_data()
    numbers = data.get('numbers', [])
    selected = next((n for n in numbers if n['id'] == number_id), None)
    
    if not selected:
        await callback.answer("❌ Номер не найден", show_alert=True)
        return
    
    invoice_result = await create_invoice(
        amount=RENT_PRICE,
        description=f"Аренда номера {selected['masked']} на 30 мин"
    )
    
    if invoice_result.get('ok'):
        invoice_data = invoice_result['result']
        invoice_id = invoice_data['invoice_id']
        invoice_url = invoice_data['pay_url']
        
        user_rentals[callback.from_user.id] = {
            'full_number': selected['full'],
            'masked_number': selected['masked'],
            'invoice_id': invoice_id,
            'paid': False,
            'number_id': number_id,
            'country_code': country_code
        }
        
        await state.set_state(RentState.waiting_payment)
        
        await callback.message.edit_text(
            f"💳 <b>Счет создан!</b>\n\n"
            f"Сумма: <b>{RENT_PRICE}$</b>\n"
            f"Номер: {selected['masked']}\n\n"
            f"Нажмите кнопку для оплаты:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить через CryptoBot", url=invoice_url)],
                [InlineKeyboardButton(text="🔔 Я оплатил", callback_data=f"check_pay_{number_id}_{country_code.replace('+', '')}")]
            ]),
            parse_mode="HTML"
        )
    else:
        error_text = invoice_result.get('error', {}).get('message', 'Неизвестная ошибка')
        logging.error(f"❌ Ошибка инвойса: {error_text}")
        await callback.message.edit_text(
            f"❌ <b>Ошибка создания счета</b>\n\n"
            f"Детали: <code>{error_text}</code>\n\n"
            f"Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
            ]),
            parse_mode="HTML"
        )

@dp.callback_query(F.data.startswith("check_pay_"))
async def check_payment(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split('_')
    number_id = int(parts[2])
    country_code = f"+{parts[3]}"
    
    user_id = callback.from_user.id
    rental_data = user_rentals.get(user_id)
    
    if not rental_data:
        await callback.answer("❌ Данные не найдены", show_alert=True)
        return
    
    status_result = await check_invoice_status(rental_data['invoice_id'])
    
    if status_result.get('ok') and status_result['result'].get('status') == 'paid':
        user_rentals[user_id]['paid'] = True
        await state.set_state(RentState.active_rent)
        
        await callback.message.edit_text(
            f"✅ <b>Оплата подтверждена!</b>\n\n"
            f"📞 Ваш номер: <code>{rental_data['full_number']}</code>\n\n"
            f"⏱ Осталось: 30 минут\n\n"
            f"Нажмите «Проверить уведомления» для получения СМС.",
            reply_markup=get_check_notification_keyboard(number_id, country_code.replace('+', '')),
            parse_mode="HTML"
        )
    else:
        status = status_result.get('result', {}).get('status', 'unknown')
        await callback.answer(f"⏳ Статус: {status}. Подождите...", show_alert=True)

@dp.callback_query(F.data.startswith("check_"))
async def check_notifications(callback: types.CallbackQuery):
    temp_msg = await callback.message.answer(
        "🔔 <i>Пока нет входящих уведомлений...</i>",
        parse_mode="HTML"
    )
    await callback.answer()
    await asyncio.sleep(5)
    try:
        await temp_msg.delete()
    except:
        pass

@dp.callback_query(F.data == "my_number_")
async def show_my_number(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    rental_data = user_rentals.get(user_id)
    if rental_data and rental_data.get('paid'):
        await callback.answer(f"📞 {rental_data['full_number']}", show_alert=True)
    else:
        await callback.answer("❌ Сначала оплатите аренду", show_alert=True)

@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "👋 <b>Главное меню</b>\n\nВыберите раздел:",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "menu_phys")
async def phys_accounts(callback: types.CallbackQuery):
    await callback.answer("🚧 Раздел в разработке. Скоро будет...", show_alert=True)

@dp.callback_query(F.data == "menu_snoser")
async def snoser(callback: types.CallbackQuery):
    await callback.answer("🚧 Раздел в разработке. Скоро будет...", show_alert=True)

# ================= ЗАПУСК =================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())