import sqlite3
import os
from datetime import datetime
from config import DATABASE_PATH

def init_db():
    """Создать базу данных"""
    # ✅ СОЗДАЕМ ПАПКУ ДЛЯ БАЗЫ
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    conn = sqlite3.connect(DATABASE_PATH)
    # ... остальной код
    cursor = conn.cursor()
    
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
    
    cursor.execute('''
    UPDATE scammers SET status = ? WHERE invoice_id = ?
    ''', (status, invoice_id))
    
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
    """Создать реферальную ссылку"""
    import base64
    ref_code = base64.b64encode(f"{user_id}_{int(time.time())}".encode()).decode()[:10]
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Создаем таблицу если нет
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        ref_code TEXT UNIQUE,
        earnings REAL DEFAULT 0,
        created_at DATETIME
    )
    ''')
    
    # Сохраняем реф-код
    cursor.execute('''
    INSERT OR REPLACE INTO referrals (user_id, ref_code, created_at)
    VALUES (?, ?, ?)
    ''', (user_id, ref_code, datetime.now()))
    
    conn.commit()
    conn.close()
    
    return ref_code

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
    
    cursor.execute('''
    UPDATE referrals SET earnings = earnings + ? WHERE user_id = ?
    ''', (amount, user_id))
    
    conn.commit()
    conn.close()

def get_referral_stats(user_id):
    """Статистика рефералов"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Считаем сколько привел
    cursor.execute('''
    SELECT COUNT(*) FROM users WHERE referred_by = (
        SELECT ref_code FROM referrals WHERE user_id = ?
    )
    ''', (user_id,))
    
    count = cursor.fetchone()[0]
    
    # Сколько заработал
    cursor.execute('SELECT earnings FROM referrals WHERE user_id = ?', (user_id,))
    earnings = cursor.fetchone()
    
    conn.close()
    return count, earnings[0] if earnings else 0

# ===== ЗАДАНИЯ (TIKTOK) =====
def create_task(user_id, task_type):
    """Создать задание"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
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
    
    reward = 0.3 if task_type == 'tiktok' else 0.2
    
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
    
    cursor.execute('''
    UPDATE tasks SET proof = ?, status = 'review' WHERE id = ?
    ''', (proof_text, task_id))
    
    conn.commit()
    conn.close()

def approve_task(task_id):
    """Одобрить задание"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Получаем задание
    cursor.execute('SELECT user_id, reward FROM tasks WHERE id = ?', (task_id,))
    task = cursor.fetchone()
    
    if task:
        user_id, reward = task
        
        # Обновляем статус
        cursor.execute('UPDATE tasks SET status = ? WHERE id = ?', ('approved', task_id))
        
        # Начисляем бонус
        cursor.execute('''
        INSERT INTO balances (user_id, amount) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET amount = amount + ?
        ''', (user_id, reward, reward))
        
        conn.commit()
        return True
    
    conn.close()
    return False

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