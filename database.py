import sqlite3
import os
import time
import base64
from datetime import datetime
from config import DATABASE_PATH

def init_db():
    """Создать все таблицы"""
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Таблица пойманных (scammers)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS scammers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        first_name TEXT,
        category_id TEXT,
        amount REAL,
        invoice_id TEXT,
        status TEXT DEFAULT 'pending',
        timestamp DATETIME
    )
    ''')
    
    # Таблица пользователей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        username TEXT,
        first_name TEXT,
        referred_by TEXT,
        registered_at DATETIME
    )
    ''')
    
    # Таблица реферальных кодов и заработка
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        ref_code TEXT UNIQUE,
        earnings REAL DEFAULT 0,
        created_at DATETIME
    )
    ''')
    
    # Таблица балансов пользователей (бонусы)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS balances (
        user_id INTEGER PRIMARY KEY,
        amount REAL DEFAULT 0
    )
    ''')
    
    # Таблица заданий
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        task_type TEXT,
        status TEXT DEFAULT 'pending',
        proof TEXT,
        reward REAL,
        created_at DATETIME
    )
    ''')
    
    conn.commit()
    conn.close()

def save_scammer(user_id, username, first_name, category_id, amount, invoice_id):
    """Сохранить данные педофила"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO scammers (user_id, username, first_name, category_id, amount, invoice_id, timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, category_id, amount, invoice_id, datetime.now()))
    conn.commit()
    conn.close()
    return cursor.lastrowid

def update_payment_status(invoice_id, status):
    """Обновить статус платежа"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE scammers SET status = ? WHERE invoice_id = ?', (status, invoice_id))
    conn.commit()
    conn.close()

def get_all_scammers():
    """Получить всех педофилов"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM scammers ORDER BY timestamp DESC')
    data = cursor.fetchall()
    conn.close()
    return data

# ===== РЕФЕРАЛЬНАЯ СИСТЕМА =====
def create_ref_link(user_id):
    """Создать реферальную ссылку (или вернуть существующую)"""
    ref_code = base64.b64encode(f"{user_id}_{int(time.time())}".encode()).decode()[:10]
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Пытаемся вставить новый код, если пользователь уже существует – игнорируем
    cursor.execute('''
    INSERT OR IGNORE INTO referrals (user_id, ref_code, created_at)
    VALUES (?, ?, ?)
    ''', (user_id, ref_code, datetime.now()))
    
    # Если запись была проигнорирована, получаем существующий код
    cursor.execute('SELECT ref_code FROM referrals WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.commit()
    conn.close()
    
    return row[0] if row else ref_code

def get_ref_code(user_id):
    """Получить реф-код пользователя"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT ref_code FROM referrals WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def add_referral_earnings(user_id, amount):
    """Добавить заработок рефереру"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE referrals SET earnings = earnings + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def get_referral_stats(user_id):
    """Статистика рефералов: сколько пригласил и сколько заработал"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Получаем реф-код пользователя
    cursor.execute('SELECT ref_code FROM referrals WHERE user_id = ?', (user_id,))
    ref = cursor.fetchone()
    count = 0
    if ref:
        cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by = ?', (ref[0],))
        count = cursor.fetchone()[0]
    
    cursor.execute('SELECT earnings FROM referrals WHERE user_id = ?', (user_id,))
    earnings = cursor.fetchone()
    
    conn.close()
    return count, earnings[0] if earnings else 0

def add_user(user_id, username, first_name, referred_by=None):
    """Добавить нового пользователя (вызывается при /start)"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT OR IGNORE INTO users (user_id, username, first_name, referred_by, registered_at)
    VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, referred_by, datetime.now()))
    conn.commit()
    conn.close()

def get_user_referrer(user_id):
    """Вернуть user_id пригласившего по реф-коду (если есть)"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT referred_by FROM users WHERE user_id = ?', (user_id,))
    ref_code = cursor.fetchone()
    if ref_code and ref_code[0]:
        cursor.execute('SELECT user_id FROM referrals WHERE ref_code = ?', (ref_code[0],))
        inviter = cursor.fetchone()
        conn.close()
        return inviter[0] if inviter else None
    conn.close()
    return None

def add_balance(user_id, amount):
    """Начислить бонус на баланс пользователя"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO balances (user_id, amount) VALUES (?, ?)
    ON CONFLICT(user_id) DO UPDATE SET amount = amount + ?
    ''', (user_id, amount, amount))
    conn.commit()
    conn.close()

def get_balance(user_id):
    """Получить баланс пользователя"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT amount FROM balances WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def get_all_users():
    """Получить список всех пользователей (для админа)"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, first_name, registered_at FROM users ORDER BY registered_at DESC')
    data = cursor.fetchall()
    conn.close()
    return data

# ===== ЗАДАНИЯ (TIKTOK) =====
def create_task(user_id, task_type):
    """Создать задание"""
    reward = 0.3 if task_type == 'tiktok' else 0.2
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO tasks (user_id, task_type, reward, created_at)
    VALUES (?, ?, ?, ?)
    ''', (user_id, task_type, reward, datetime.now()))
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id

def submit_task_proof(task_id, proof_text):
    """Отправить подтверждение задания"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE tasks SET proof = ?, status = ? WHERE id = ?', (proof_text, 'review', task_id))
    conn.commit()
    conn.close()

def approve_task(task_id):
    """Одобрить задание. Возвращает (user_id, reward) или None"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT user_id, reward FROM tasks WHERE id = ? AND status = ?', (task_id, 'review'))
    task = cursor.fetchone()
    if task:
        user_id, reward = task
        cursor.execute('UPDATE tasks SET status = ? WHERE id = ?', ('approved', task_id))
        cursor.execute('''
        INSERT INTO balances (user_id, amount) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET amount = amount + ?
        ''', (user_id, reward, reward))
        conn.commit()
        conn.close()
        return user_id, reward
    conn.close()
    return None

def get_pending_tasks():
    """Получить задания на проверку"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    SELECT id, user_id, task_type, proof, created_at FROM tasks 
    WHERE status = 'review' ORDER BY created_at DESC
    ''')
    tasks = cursor.fetchall()
    conn.close()
    return tasks
