import random
import string
from datetime import datetime

def generate_session_string():
    chars = string.ascii_letters + string.digits + '-_'
    return '1' + ''.join(random.choice(chars) for _ in range(350))

def generate_account_data(account_type):
    if account_type in ['usa_new', 'ru_new', 'ua_new']:
        phone = generate_phone(account_type)
        return {
            'phone': phone,
            'session': generate_session_string(),
            'username': f"user_{random.randint(10000, 99999)}",
            'password': ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(12)),
            'created': datetime.now().strftime('%Y-%m-%d')
        }
    
    elif account_type == 'asia_aged':
        countries = ['+62', '+66', '+84', '+60', '+63']
        country = random.choice(countries)
        return {
            'phone': f"{country}{''.join([str(random.randint(0, 9)) for _ in range(10)])}",
            'session': generate_session_string(),
            'username': f"asia_{random.randint(1000, 9999)}",
            'aged_years': random.randint(5, 9),
            'password': ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(12))
        }
    
    elif account_type.startswith('ru_20'):
        year = account_type.split('_')[1]
        return {
            'phone': f"+7{''.join([str(random.randint(0, 9)) for _ in range(10)])}",
            'session': generate_session_string(),
            'username': f"ru{year}_{random.randint(100, 999)}",
            'registered': f"{year}-0{random.randint(1, 9)}-{random.randint(10, 28)}",
            'password': ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(12))
        }
    
    elif account_type == 'premium_month':
        return {
            'type': 'premium_activation',
            'code': f"PREM-{random.randint(100000, 999999)}",
            'valid_until': (datetime.now().replace(month=datetime.now().month + 1 if datetime.now().month < 12 else 1)).strftime('%Y-%m-%d')
        }
    
    return {}

def generate_phone(account_type):
    if account_type == 'usa_new':
        return f"+1{''.join([str(random.randint(0, 9)) for _ in range(10)])}"
    elif account_type == 'ru_new':
        return f"+7{''.join([str(random.randint(0, 9)) for _ in range(10)])}"
    elif account_type == 'ua_new':
        return f"+380{''.join([str(random.randint(0, 9)) for _ in range(9)])}"
    return "+0000000000"
