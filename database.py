import sqlite3
import random
from datetime import datetime, timedelta

DB_NAME = 'gogogo.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Таблица номеров (аренда)
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
    
    # Таблица покупок (аренда)
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
    
    # 🛒 Таблица физ аккаунтов (инвентарь)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS phys_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_type TEXT,
            phone TEXT,
            session TEXT,
            username TEXT,
            password TEXT,
            extra_data TEXT,
            is_sold INTEGER DEFAULT 0,
            sold_to INTEGER,
            sold_at TEXT
        )
    ''')
    
    # 🛒 Таблица покупок физ аккаунтов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS phys_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            account_type TEXT,
            account_id INTEGER,
            price REAL,
            quantity INTEGER DEFAULT 1,
            created_at TEXT
        )
    ''')
    
    # Таблица cooldown
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cooldowns (
            user_id INTEGER PRIMARY KEY,
            last_invoice TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def fill_phys_accounts():
    """Заполняет базу физ аккаунтами при первом запуске"""
    from config import PHYS_ACCOUNTS
    from accounts import generate_account_data
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    for account_type, data in PHYS_ACCOUNTS.items():
        cursor.execute("SELECT COUNT(*) FROM phys_accounts WHERE account_type = ?", (account_type,))
        count = cursor.fetchone()[0]
        
        # Генерируем по 20 аккаунтов каждого типа
        if count < 20:
            to_generate = 20 - count
            for _ in range(to_generate):
                acc_data = generate_account_data(account_type)
                try:
                    cursor.execute(
                        """INSERT INTO phys_accounts 
                        (account_type, phone, session, username, password, extra_data) 
                        VALUES (?, ?, ?, ?, ?, ?)""",
                        (account_type, 
                         acc_data.get('phone', ''), 
                         acc_data.get('session', ''), 
                         acc_data.get('username', ''), 
                         acc_data.get('password', ''),
                         str(acc_data))
                    )
                except sqlite3.IntegrityError:
                    pass
    
    conn.commit()
    conn.close()

def get_available_phys_accounts(account_type, quantity=1):
    """Получает свободные аккаунты"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, account_type, phone, session, username, password, extra_data FROM phys_accounts WHERE account_type = ? AND is_sold = 0 LIMIT ?",
        (account_type, quantity)
    )
    rows = cursor.fetchall()
    conn.close()
    
    return [{
        'id': r[0],
        'account_type': r[1],
        'phone': r[2],
        'session': r[3],
        'username': r[4],
        'password': r[5],
        'extra_data': r[6]
    } for r in rows]

def sell_phys_account(account_id, user_id, price):
    """Помечает аккаунт как проданный"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE phys_accounts SET is_sold = 1, sold_to = ?, sold_at = ? WHERE id = ?",
        (user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), account_id)
    )
    
    cursor.execute("SELECT account_type FROM phys_accounts WHERE id = ?", (account_id,))
    row = cursor.fetchone()
    
    if row:
        cursor.execute(
            "INSERT INTO phys_purchases (user_id, account_type, account_id, price, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, row[0], account_id, price, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
    
    conn.commit()
    conn.close()
    return row

def get_user_phys_purchases(user_id):
    """Получает историю покупок физ аккаунтов"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """SELECT p.account_type, p.price, p.created_at, a.phone, a.username, a.password, a.extra_data 
        FROM phys_purchases p 
        JOIN phys_accounts a ON p.account_id = a.id 
        WHERE p.user_id = ? ORDER BY p.id DESC LIMIT 10""",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    return [{
        'type': r[0],
        'price': r[1],
        'created': r[2],
        'phone': r[3],
        'username': r[4],
        'password': r[5],
        'extra': r[6]
    } for r in rows]

def check_cooldown(user_id, cooldown_seconds=60):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT last_invoice FROM cooldowns WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if row:
        last_time = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
        if datetime.now() - last_time < timedelta(seconds=cooldown_seconds):
            conn.close()
            return False
    
    cursor.execute("INSERT OR REPLACE INTO cooldowns (user_id, last_invoice) VALUES (?, ?)",
                   (user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    return True

# Инициализация
init_db()
fill_phys_accounts()
