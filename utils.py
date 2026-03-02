import logging
import os
from config import LOG_PATH

def setup_logger():
    """Настроить логирование"""
    # ✅ СОЗДАЕМ ПАПКУ ДЛЯ ЛОГОВ
    log_dir = os.path.dirname(LOG_PATH)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_PATH, encoding='utf-8'),  # ✅ Добавлена кодировка
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)

def format_scammer_info(scammer):
    """Форматировать данные педофила для админа"""
    text = f"🔴 *Пойман педофил!*\n\n"
    text += f"👤 *ID:* `{scammer[1]}`\n"
    text += f"📛 *Username:* @{scammer[2] if scammer[2] else 'нет'}\n"
    text += f"📝 *Имя:* {scammer[3]}\n"
    text += f"📁 *Категория:* {scammer[4]}\n"
    text += f"💰 *Сумма:* {scammer[5]} USDT\n"
    text += f"🧾 *Инвойс:* `{scammer[6]}`\n"
    text += f"📊 *Статус:* {scammer[7]}\n"
    text += f"⏰ *Время:* {scammer[8]}"
    return text