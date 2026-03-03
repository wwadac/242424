import asyncio
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from config import BOT_TOKEN, ADMIN_ID, MIN_PRICE, MAX_PRICE, TEMP_PATH
from catalog import (
    get_catalog, get_category, format_category_text,
    get_popular_categories, get_categories_by_price,
    get_categories_by_tag
)
from database import (
    init_db, save_scammer, get_all_scammers, update_payment_status,
    create_ref_link, get_ref_code, get_referral_stats,
    add_user, add_balance, add_referral_earnings, get_all_users,
    create_task, submit_task_proof, approve_task
)
from payments import create_invoice, check_invoice_status
from utils import setup_logger, format_scammer_info
from texts import WELCOME_TEXT, HELP_TEXT
import os

# Инициализация
logger = setup_logger()
init_db()

# Хранилище данных пользователей
user_data = {}

# ===== ГЛАВНОЕ МЕНЮ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start - главное меню + обработка рефералов"""
    user = update.effective_user
    args = context.args

    # Реферальная логика
    referred_by = None
    if args and args[0].startswith('ref_'):
        ref_code = args[0][4:]  # убираем 'ref_'
        # Находим владельца кода
        conn = sqlite3.connect('data/scammers.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM referrals WHERE ref_code = ?', (ref_code,))
        inviter = cursor.fetchone()
        conn.close()
        if inviter:
            referred_by = ref_code
            # Начисляем бонус пригласившему (0.2)
            add_referral_earnings(inviter[0], 0.2)
            # Начисляем бонус новому пользователю (0.1)
            add_balance(user.id, 0.1)
            await context.bot.send_message(
                inviter[0],
                f"🎉 По вашей реферальной ссылке зарегистрировался {user.first_name}! Начислено 0.2 USDT."
            )

    # Сохраняем пользователя
    add_user(user.id, user.username, user.first_name, referred_by)

    # Клавиатура главного меню
    keyboard = [
        [InlineKeyboardButton("📁 Весь каталог", callback_data="main_catalog")],
        [InlineKeyboardButton("🔥 Популярное", callback_data="main_popular")],
        [InlineKeyboardButton("💰 По цене", callback_data="main_by_price")],
        [InlineKeyboardButton("🔍 Поиск по тегам", callback_data="main_search")],
        [InlineKeyboardButton("🎯 Задания и бонусы", callback_data="main_tasks")],
        [InlineKeyboardButton("👥 Рефералы", callback_data="task_ref")],
        [InlineKeyboardButton("💎 VIP раздел", callback_data="main_vip")],
        [InlineKeyboardButton("🌐 По странам", callback_data="main_countries")],
        [InlineKeyboardButton("📦 Пакеты", callback_data="main_packs")],
        [InlineKeyboardButton("❓ Помощь", callback_data="main_help")]
    ]

    if user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👑 Админ панель", callback_data="admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        WELCOME_TEXT,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ===== ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ МЕНЮ =====
async def show_catalog(query):
    """Показать весь каталог"""
    catalog = get_catalog()
    keyboard = []

    for cat_id, cat_data in list(catalog.items())[:15]:
        keyboard.append([InlineKeyboardButton(
            f"{cat_data['name']} - {cat_data['price']} USDT",
            callback_data=f"cat_{cat_id}"
        )])

    keyboard.append([InlineKeyboardButton("◀️ В главное меню", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "📁 *Весь каталог*\n\n"
        f"Всего позиций: {len(catalog)}\n"
        f"Цены: от {MIN_PRICE} до {MAX_PRICE} USDT",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_popular(query):
    """Показать популярное"""
    popular = get_popular_categories(10)

    text = "🔥 *Популярные категории*\n\n"

    keyboard = []
    for cat_id, cat_data in popular.items():
        text += f"• {cat_data['name']} - {cat_data['popularity']:,} просмотров\n"
        keyboard.append([InlineKeyboardButton(
            f"{cat_data['name']} - {cat_data['price']} USDT",
            callback_data=f"cat_{cat_id}"
        )])

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_price_menu(query):
    """Меню выбора по цене"""
    keyboard = [
        [InlineKeyboardButton("💰 До 1 USDT", callback_data="price_0_1")],
        [InlineKeyboardButton("💰 1-3 USDT", callback_data="price_1_3")],
        [InlineKeyboardButton("💰 3-5 USDT", callback_data="price_3_5")],
        [InlineKeyboardButton("💰 5-8 USDT", callback_data="price_5_8")],
        [InlineKeyboardButton("💰 8-12 USDT", callback_data="price_8_12")],
        [InlineKeyboardButton("💰 12-15 USDT", callback_data="price_12_15")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "💰 *Выберите ценовой диапазон:*\n\n"
        f"Минимальная цена: {MIN_PRICE} USDT\n"
        f"Максимальная цена: {MAX_PRICE} USDT",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_price_range(query, min_p, max_p):
    """Показать категории по цене"""
    categories = get_categories_by_price(min_p, max_p)

    if not categories:
        await query.edit_message_text(
            f"❌ В диапазоне {min_p}-{max_p} USDT ничего не найдено",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="main_by_price")
            ]])
        )
        return

    text = f"💰 *Цены {min_p}-{max_p} USDT*\n\n"
    keyboard = []

    for cat_id, cat_data in list(categories.items())[:10]:
        text += f"• {cat_data['name']} - {cat_data['price']} USDT\n"
        keyboard.append([InlineKeyboardButton(
            f"{cat_data['name']} - {cat_data['price']} USDT",
            callback_data=f"cat_{cat_id}"
        )])

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="main_by_price")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_search_tags(query):
    """Показать поиск по тегам"""
    keyboard = [
        [InlineKeyboardButton("🏷️ HD качество", callback_data="tag_hd")],
        [InlineKeyboardButton("🏷️ Скрытая камера", callback_data="tag_скрытая камера")],
        [InlineKeyboardButton("🏷️ Домашнее", callback_data="tag_домашнее")],
        [InlineKeyboardButton("🏷️ Школа", callback_data="tag_школа")],
        [InlineKeyboardButton("🏷️ Детсад", callback_data="tag_детсад")],
        [InlineKeyboardButton("🏷️ Жесткое", callback_data="tag_жесткое")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🔍 *Поиск по тегам*\n\n"
        "Выберите интересующий тег:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_vip(query):
    """Показать VIP раздел"""
    keyboard = [
        [InlineKeyboardButton("👑 VIP: Полный доступ - 15.0 USDT", callback_data="cat_vip_1")],
        [InlineKeyboardButton("👑 VIP: Telegram чаты - 10.0 USDT", callback_data="cat_vip_2")],
        [InlineKeyboardButton("👑 VIP: Даркнет гид - 8.0 USDT", callback_data="cat_vip_3")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "💎 *VIP РАЗДЕЛ*\n\n"
        "Только для избранных. Эксклюзивный контент.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_countries(query):
    """Показать раздел по странам"""
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Россия - 5.0 USDT", callback_data="cat_country_1")],
        [InlineKeyboardButton("🇺🇦 Украина - 4.5 USDT", callback_data="cat_country_2")],
        [InlineKeyboardButton("🇧🇾 Беларусь - 4.0 USDT", callback_data="cat_country_3")],
        [InlineKeyboardButton("🇪🇺 Европа - 6.0 USDT", callback_data="cat_country_4")],
        [InlineKeyboardButton("🇺🇸 USA - 7.0 USDT", callback_data="cat_country_5")],
        [InlineKeyboardButton("🌏 Азия - 5.5 USDT", callback_data="cat_country_6")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🌐 *По странам*\n\n"
        "Выберите страну:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_packs(query):
    """Показать пакеты"""
    keyboard = [
        [InlineKeyboardButton("📦 Пакет 'Начинающий' - 3.0 USDT", callback_data="cat_pack_1")],
        [InlineKeyboardButton("📦 Пакет 'Продвинутый' - 7.0 USDT", callback_data="cat_pack_2")],
        [InlineKeyboardButton("📦 Пакет 'Профессионал' - 12.0 USDT", callback_data="cat_pack_3")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "📦 *Пакеты*\n\n"
        "Готовые сборники по лучшей цене:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_help(query):
    """Показать помощь"""
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        HELP_TEXT,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_category(query, cat_id, user):
    """Показать категорию"""
    cat_data = get_category(cat_id)

    if cat_data:
        user_data[user.id] = {'category': cat_id, 'amount': cat_data['price']}

        text = format_category_text(cat_id, cat_data)

        keyboard = [
            [InlineKeyboardButton("💳 Оплатить", callback_data=f"pay_{cat_id}")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_catalog")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def process_payment(query, cat_id, user):
    """Обработка платежа"""
    cat_data = get_category(cat_id)

    if cat_data and user.id in user_data:
        invoice = create_invoice(cat_data['price'], cat_data['name'])

        if invoice:
            save_scammer(
                user.id, user.username, user.first_name,
                cat_id, cat_data['price'], invoice['invoice_id']
            )

            keyboard = [
                [InlineKeyboardButton("💵 Перейти к оплате", url=invoice['pay_url'])],
                [InlineKeyboardButton("✅ Я оплатил", callback_data=f"check_{invoice['invoice_id']}")],
                [InlineKeyboardButton("◀️ Назад", callback_data="back_to_catalog")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                f"🧾 *Счет создан!*\n\n"
                f"💰 Сумма: {cat_data['price']} USDT\n"
                f"📦 Товар: {cat_data['name']}\n"
                f"⏳ Счет действителен 1 час\n\n"
                f"✅ После оплаты контент придет автоматически.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text("❌ Ошибка создания счета")

async def check_payment(query, invoice_id, user, context):
    """Проверка оплаты"""
    status = check_invoice_status(invoice_id)

    if status == 'paid':
        update_payment_status(invoice_id, 'paid')

        await query.edit_message_text(
            "❌ *Доступ запрещен*\n\n"
            "Ваш аккаунт заблокирован. "
            "Все данные переданы в правоохранительные органы.",
            parse_mode='Markdown'
        )

        amount = user_data.get(user.id, {}).get('amount', '?')
        await context.bot.send_message(
            ADMIN_ID,
            f"🔴 *ПОЙМАН ПЕДОФИЛ!*\n\n"
            f"👤 ID: `{user.id}`\n"
            f"📛 Username: @{user.username if user.username else 'нет'}\n"
            f"📝 Имя: {user.first_name}\n"
            f"💰 Сумма: {amount} USDT",
            parse_mode='Markdown'
        )

        if user.id in user_data:
            del user_data[user.id]
    else:
        await query.edit_message_text(
            "⏳ Платеж не найден.\n\n"
            "Если вы оплатили, подождите 1-2 минуты и попробуйте снова.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ В каталог", callback_data="back_to_catalog")
            ]])
        )

# ===== РЕФЕРАЛЬНАЯ СИСТЕМА =====
async def ref_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Реферальная система (вызывается из callback)"""
    query = update.callback_query
    await query.answer()
    user = query.from_user

    ref_code = get_ref_code(user.id)
    if not ref_code:
        ref_code = create_ref_link(user.id)

    count, earnings = get_referral_stats(user.id)
    bot_username = (await context.bot.get_me()).username

    text = f"""
👥 *РЕФЕРАЛЬНАЯ СИСТЕМА*

💰 *Ваши рефералы:* {count}
💵 *Заработано:* {earnings} USDT

🔗 *Ваша ссылка:*
`https://t.me/{bot_username}?start=ref_{ref_code}`

📊 *Как это работает:*
• Приглашайте друзей
• Получайте 0.2 USDT за каждого
• Друзья получают бонус 0.1 USDT на первый заказ

🎁 *Партнерская программа:*
• Приведи 10 друзей → +1 USDT бонус
• Приведи 50 друзей → VIP статус
"""

    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ===== ЗАДАНИЯ =====
async def tasks_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню заданий"""
    query = update.callback_query
    await query.answer()

    text = """
🎯 *ЗАДАНИЯ И БОНУСЫ*

📱 *TikTok задание:* 0.3 USDT
1. Напиши в комментариях: `Юз бота - @твой_бот тут детское`
2. Сделай скриншот
3. Отправь на проверку

👥 *Рефералы:* 0.2 USDT за друга

✅ Минимальная выплата: 1 USDT
"""

    keyboard = [
        [InlineKeyboardButton("📱 Выполнить TikTok", callback_data="task_tiktok")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def task_tiktok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Задание TikTok"""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    task_id = create_task(user.id, 'tiktok')

    text = """
📱 *TIKTOK ЗАДАНИЕ (0.3 USDT)*

*ШАГ 1:* Напиши под любым видео комментарий:
`Юз бота - @твой_бот тут детское`

*ШАГ 2:* Сделай скриншот

*ШАГ 3:* Отправь скриншот сюда (прикрепи фото)

⏳ После проверки получишь 0.3 USDT
"""

    context.user_data['current_task'] = task_id

    keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка фото"""
    if 'current_task' not in context.user_data:
        await update.message.reply_text("Сначала выбери задание в меню")
        return

    task_id = context.user_data['current_task']
    photo = update.message.photo[-1]
    file = await photo.get_file()

    os.makedirs(TEMP_PATH, exist_ok=True)
    file_path = f"{TEMP_PATH}task_{task_id}_{update.effective_user.id}.jpg"
    await file.download_to_drive(file_path)

    caption = f"📸 *Новое задание*\n\n"
    caption += f"👤 Пользователь: {update.effective_user.id}\n"
    caption += f"📝 Username: @{update.effective_user.username}\n"
    caption += f"🆔 Task ID: {task_id}\n"
    caption += f"💰 Награда: 0.3 USDT"

    keyboard = [[
        InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_task_{task_id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    with open(file_path, 'rb') as photo_file:
        await context.bot.send_photo(
            ADMIN_ID, photo_file, caption=caption,
            reply_markup=reply_markup, parse_mode='Markdown'
        )

    submit_task_proof(task_id, file_path)
    await update.message.reply_text("✅ Скриншот отправлен на проверку!")
    del context.user_data['current_task']

async def admin_approve_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ одобряет задание"""
    query = update.callback_query
    await query.answer()

    task_id = int(query.data.split('_')[-1])
    result = approve_task(task_id)  # возвращает (user_id, reward) или None

    if result:
        user_id, reward = result
        await query.edit_message_caption(
            caption=query.message.caption + f"\n\n✅ ЗАДАНИЕ ОДОБРЕНО! {reward} USDT начислено."
        )
        await context.bot.send_message(
            user_id,
            f"✅ Ваше задание одобрено! На ваш баланс зачислено {reward} USDT."
        )
    else:
        await query.edit_message_caption(
            caption=query.message.caption + "\n\n❌ ОШИБКА: задание не найдено или уже обработано."
        )

async def back_to_main(query):
    """Вернуться в главное меню"""
    keyboard = [
        [InlineKeyboardButton("📁 Весь каталог", callback_data="main_catalog")],
        [InlineKeyboardButton("🔥 Популярное", callback_data="main_popular")],
        [InlineKeyboardButton("💰 По цене", callback_data="main_by_price")],
        [InlineKeyboardButton("🔍 Поиск по тегам", callback_data="main_search")],
        [InlineKeyboardButton("🎯 Задания и бонусы", callback_data="main_tasks")],
        [InlineKeyboardButton("👥 Рефералы", callback_data="task_ref")],
        [InlineKeyboardButton("💎 VIP раздел", callback_data="main_vip")],
        [InlineKeyboardButton("🌐 По странам", callback_data="main_countries")],
        [InlineKeyboardButton("📦 Пакеты", callback_data="main_packs")],
        [InlineKeyboardButton("❓ Помощь", callback_data="main_help")]
    ]

    if query.from_user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👑 Админ панель", callback_data="admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        WELCOME_TEXT,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ===== АДМИН ПАНЕЛЬ (полностью переписана с добавлением кнопки "Все пользователи") =====
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ панель"""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("👥 Все педофилы", callback_data="admin_all")],
        [InlineKeyboardButton("👥 Все пользователи", callback_data="admin_users")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("💰 Доход", callback_data="admin_income")],
        [InlineKeyboardButton("📁 Последние 10", callback_data="admin_last10")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "👑 *Админ панель*\n\n"
        "Выберите действие:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def admin_all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать всех пользователей"""
    query = update.callback_query
    await query.answer()

    users = get_all_users()
    if not users:
        await query.edit_message_text("👥 В базе пока нет пользователей.")
        return

    text = f"👥 *Всего пользователей:* {len(users)}\n\n"
    for u in users[:50]:  # первые 50
        user_id, username, first_name, reg_date = u
        name = first_name or "—"
        user_tag = f"@{username}" if username else "—"
        text += f"• {name} ({user_tag}) — `{user_id}`\n   зарегистрирован: {reg_date[:10]}\n"

    if len(users) > 50:
        text += f"\n... и ещё {len(users)-50}"

    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка админ кнопок"""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "admin_all":
        scammers = get_all_scammers()
        if not scammers:
            await query.edit_message_text("📊 База пуста")
            return

        text = f"📊 *Всего поймано:* {len(scammers)}\n\n"
        for scammer in scammers:
            text += f"• {scammer[3]} (@{scammer[2]}) - {scammer[5]} USDT - {scammer[8]}\n"
            if len(text) > 3000:
                text += "..."
                break

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif data == "admin_last10":
        scammers = get_all_scammers()
        if not scammers:
            await query.edit_message_text("📊 База пуста")
            return

        text = "📁 *Последние 10 педофилов:*\n\n"
        for scammer in scammers[-10:]:
            text += f"• {scammer[3]} (@{scammer[2]}) - {scammer[5]} USDT\n"

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif data == "admin_stats":
        scammers = get_all_scammers()
        if not scammers:
            await query.edit_message_text("📊 База пуста")
            return

        total = len(scammers)
        total_sum = sum([s[5] for s in scammers])
        avg = total_sum / total if total > 0 else 0
        unique_users = len(set([s[1] for s in scammers]))

        text = f"📊 *СТАТИСТИКА*\n\n"
        text += f"👥 Всего педофилов: {total}\n"
        text += f"👤 Уникальных: {unique_users}\n"
        text += f"💰 Общий доход: {total_sum:.2f} USDT\n"
        text += f"📈 Средний чек: {avg:.2f} USDT\n"

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif data == "admin_income":
        scammers = get_all_scammers()
        if not scammers:
            await query.edit_message_text("📊 Нет данных")
            return

        total = sum([s[5] for s in scammers])

        text = f"💰 *ДОХОД*\n\n"
        text += f"Всего заработано: {total:.2f} USDT\n"

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif data == "admin_users":
        await admin_all_users(update, context)

# ===== ОБРАБОТЧИК КНОПОК =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка всех кнопок"""
    query = update.callback_query
    await query.answer()

    data = query.data
    user = query.from_user

    # Главное меню
    if data == "main_catalog":
        await show_catalog(query)
    elif data == "main_popular":
        await show_popular(query)
    elif data == "main_by_price":
        await show_price_menu(query)
    elif data == "main_search":
        await show_search_tags(query)
    elif data == "main_vip":
        await show_vip(query)
    elif data == "main_countries":
        await show_countries(query)
    elif data == "main_packs":
        await show_packs(query)
    elif data == "main_help":
        await show_help(query)
    elif data == "main_tasks":
        await tasks_menu(update, context)
    elif data == "task_ref":
        await ref_system(update, context)
    elif data.startswith("approve_task_"):
        await admin_approve_task(update, context)

    # Ценовые диапазоны
    elif data == "price_0_1":
        await show_price_range(query, 0, 1)
    elif data == "price_1_3":
        await show_price_range(query, 1, 3)
    elif data == "price_3_5":
        await show_price_range(query, 3, 5)
    elif data == "price_5_8":
        await show_price_range(query, 5, 8)
    elif data == "price_8_12":
        await show_price_range(query, 8, 12)
    elif data == "price_12_15":
        await show_price_range(query, 12, 15)

    # Админка
    elif data == "admin_panel" and user.id == ADMIN_ID:
        await admin_panel(update, context)
    elif data.startswith("admin_") and user.id == ADMIN_ID:
        await admin_callback(update, context)

    # Категории
    elif data.startswith('cat_'):
        cat_id = data.replace('cat_', '')
        await show_category(query, cat_id, user)

    # Теги
    elif data.startswith('tag_'):
        tag = data.replace('tag_', '')
        categories = get_categories_by_tag(tag)

        if not categories:
            await query.edit_message_text(
                f"❌ По тегу '{tag}' ничего не найдено",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data="main_search")
                ]])
            )
            return

        text = f"🏷️ *Тег: {tag}*\n\n"
        keyboard = []
        for cat_id, cat_data in list(categories.items())[:10]:
            text += f"• {cat_data['name']} - {cat_data['price']} USDT\n"
            keyboard.append([InlineKeyboardButton(
                f"{cat_data['name']} - {cat_data['price']} USDT",
                callback_data=f"cat_{cat_id}"
            )])

        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="main_search")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    # Оплата
    elif data.startswith('pay_'):
        cat_id = data.replace('pay_', '')
        await process_payment(query, cat_id, user)
    elif data.startswith('check_'):
        invoice_id = data.replace('check_', '')
        await check_payment(query, invoice_id, user, context)

    # Назад
    elif data == "back_to_main":
        await back_to_main(query)
    elif data == "back_to_catalog":
        await show_catalog(query)
    elif data == "task_tiktok":
        await task_tiktok(update, context)

# ===== ЗАПУСК =====
def main():
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()

    # Хендлеры
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Запуск
    logger.info("MEGA БОТ ЗАПУЩЕН! Каталог: 50+ позиций, цены 0.5-15 USDT")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
