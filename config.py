# ================= ТОКЕНЫ =================
API_TOKEN = '8500113818:AAEIG8aABNiwbCXLq08KzxJ1fkv1PhJtnqQ'
CRYPTOBOT_TOKEN = '528164:AAfmR2y2vzP5sM0Miv5HHW48oyEW3DVB3Er'

# ================= АДМИН =================
ADMIN_ID = 8000395560

# ================= АРЕНДА НОМЕРОВ =================
RENT_PRICE = 1.5
RENT_DURATION = 30  # минут
NUMBERS_PER_PAGE = 5

# ================= СТРАНЫ (5 ШТ) =================
COUNTRIES = {
    'russia': {'code': '+7', 'name': 'Россия', 'flag': '🇷🇺', 'count': 15},
    'usa': {'code': '+1', 'name': 'США', 'flag': '🇺🇸', 'count': 15},
    'india': {'code': '+91', 'name': 'Индия', 'flag': '🇮🇳', 'count': 5},
    'pakistan': {'code': '+92', 'name': 'Пакистан', 'flag': '🇵🇰', 'count': 5},
    'ukraine': {'code': '+380', 'name': 'Украина', 'flag': '🇺🇦', 'count': 5},
}

# ================= ФИЗ АККАУНТЫ =================
PHYS_ACCOUNTS = {
    'usa_new': {
        'name': '🇺🇸 США +1 (Новый)',
        'price': 1.6,
        'bulk_price': 1.3,
        'bulk_min': 10,
        'description': 'Без спамблока, без 2FA, быстрая выдача'
    },
    'ru_new': {
        'name': '🇷🇺 Новорег РФ',
        'price': 3.5,
        'bulk_price': 3.2,
        'bulk_min': 10,
        'description': 'Свежая регистрация, готов к работе'
    },
    'ua_new': {
        'name': '🇺🇦 Новорег УКР',
        'price': 3.3,
        'bulk_price': 2.8,
        'bulk_min': 10,
        'description': 'Украинский номер, без привязок'
    },
    'asia_aged': {
        'name': '🌏 Азия отлежка 5-9 лет',
        'price': 6.0,
        'bulk_price': None,
        'bulk_min': None,
        'description': 'Рандом страна, отлежка 5-9 лет'
    },
    'ru_2020': {
        'name': '🇷🇺 РФ 2020',
        'price': 8.0,
        'bulk_price': None,
        'bulk_min': None,
        'description': 'Отлежка с 2020 года'
    },
    'ru_2019': {
        'name': '🇷🇺 РФ 2019',
        'price': 9.5,
        'bulk_price': None,
        'bulk_min': None,
        'description': 'Отлежка с 2019 года'
    },
    'ru_2018': {
        'name': '🇷🇺 РФ 2018',
        'price': 11.0,
        'bulk_price': None,
        'bulk_min': None,
        'description': 'Отлежка с 2018 года'
    },
    'ru_2017': {
        'name': '🇷🇺 РФ 2017',
        'price': 13.5,
        'bulk_price': None,
        'bulk_min': None,
        'description': 'Отлежка с 2017 года'
    },
    'ru_2016': {
        'name': '🇷🇺 РФ 2016',
        'price': 16.0,
        'bulk_price': None,
        'bulk_min': None,
        'description': 'Отлежка с 2016 года'
    },
    'premium_month': {
        'name': '💎 Telegram Premium (1 месяц)',
        'price': 4.5,
        'bulk_price': None,
        'bulk_min': None,
        'description': 'Со входом, активация на ваш аккаунт'
    },
}

# ================= АНТИ-СПАМ =================
INVOICE_COOLDOWN = 60  # секунд
