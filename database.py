import sqlite3
import random
from datetime import datetime

DB_NAME = 'gogogo.db'

def init_db():
    """Создаёт таблицы при первом запуске"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Таблица номеров
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_number TEXT UNIQUE,
            masked_number TEXT,
            country TEXT,
            is_rented INTEGER DEFAULT 0,
            rented_by INTEGER,
            rented_until TEXT
        )
    ''')
    
    # Таблица покупок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            number_id INTEGER,
            full_number TEXT,
            country TEXT,
            price REAL,
            created_at TEXT,
            expired_at TEXT
        )
    ''')
    
    # Таблица cooldown (анти-спам)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cooldowns (
            user_id INTEGER PRIMARY KEY,
            last_invoice TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def generate_number(country_code):
    """Генерирует номер с маскировкой"""
    if country_code == "+7":
        digits = ''.join([str(random.randint(0, 9)) for _ in range(10)])
        full = f"+7{digits}"
        masked = f"+7{digits[:3]}*{digits[-5:]}*"
    elif country_code == "+1":
        digits = ''.join([str(random.randint(0, 9)) for _ in range(10)])
        full = f"+1{digits}"
        masked = f"+1{digits[:3]}*{digits[-5:]}*"
    elif country_code == "+91":
        digits = ''.join([str(random.randint(0, 9)) for _ in range(10)])
        full = f"+91{digits}"
        masked = f"+91{digits[:3]}*{digits[-5:]}*"
    elif country_code == "+92":
        digits = ''.join([str(random.randint(0, 9)) for _ in range(10)])
        full = f"+92{digits}"
        masked = f"+92{digits[:3]}*{digits[-5:]}*"
    elif country_code == "+380":
        digits = ''.join([str(random.randint(0, 9)) for _ in range(9)])
        full = f"+380{digits}"
        masked = f"+380{digits[:3]}*{digits[-4:]}*"
    else:
        return None, None
    return full, masked

def fill_database():
    """Заполняет базу номерами при первом запуске"""
    from config import COUNTRIES
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    for country_key, data in COUNTRIES.items():
        cursor.execute("SELECT COUNT(*) FROM numbers WHERE country = ?", (country_key,))
        count = cursor.fetchone()[0]
        
        if count < data['count']:
            to_generate = data['count'] - count
            for _ in range(to_generate):
                full, masked = generate_number(data['code'])
                try:
                    cursor.execute(
                        "INSERT INTO numbers (full_number, masked_number, country) VALUES (?, ?, ?)",
                        (full, masked, country_key)
                    )
                except sqlite3.IntegrityError:
                    pass  # Номер уже есть
    
    conn.commit()
    conn.close()

def get_available_numbers(country_key, limit=5):
    """Получает свободные номера"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, full_number, masked_number, country FROM numbers WHERE country = ? AND is_rented = 0 LIMIT ?",
        (country_key, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    
    return [{'id': r[0], 'full': r[1], 'masked': r[2], 'country': r[3]} for r in rows]

def rent_number(number_id, user_id, duration_minutes=30):
    """Арендует номер"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    from datetime import timedelta
    expired_at = datetime.now() + timedelta(minutes=duration_minutes)
    
    cursor.execute(
        "UPDATE numbers SET is_rented = 1, rented_by = ?, rented_until = ? WHERE id = ?",
        (user_id, expired_at.strftime('%Y-%m-%d %H:%M:%S'), number_id)
    )
    
    cursor.execute("SELECT full_number, masked_number, country FROM numbers WHERE id = ?", (number_id,))
    row = cursor.fetchone()
    
    if row:
        cursor.execute(
            "INSERT INTO purchases (user_id, number_id, full_number, country, price, created_at, expired_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, number_id, row[0], row[2], 1.5, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), expired_at.strftime('%Y-%m-%d %H:%M:%S'))
        )
    
    conn.commit()
    conn.close()
    return row

def get_user_purchases(user_id):
    """Получает историю покупок пользователя"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT full_number, country, created_at, expired_at, price FROM purchases WHERE user_id = ? ORDER BY id DESC LIMIT 10",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    return [{'full': r[0], 'country': r[1], 'created': r[2], 'expired': r[3], 'price': r[4]} for r in rows]

def check_cooldown(user_id, cooldown_seconds=60):
    """Проверяет анти-спам"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT last_invoice FROM cooldowns WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if row:
        from datetime import datetime, timedelta
        last_time = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
        if datetime.now() - last_time < timedelta(seconds=cooldown_seconds):
            conn.close()
            return False
    
    # Обновляем cooldown
    cursor.execute("INSERT OR REPLACE INTO cooldowns (user_id, last_invoice) VALUES (?, ?)",
                   (user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    return True

# Инициализация при импорте
init_db()
fill_database()
