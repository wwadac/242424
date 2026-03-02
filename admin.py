from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from database import get_all_scammers
from utils import format_scammer_info

async def admin_panel(query, context):
    """Админ панель"""
    user = query.from_user
    
    keyboard = [
        [InlineKeyboardButton("👥 Все педофилы", callback_data="admin_all")],
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

async def admin_callback(update: Update, context):
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
            if len(text) > 3000:  # Telegram лимит
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
        
        # Уникальные пользователи
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