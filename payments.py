import requests
import json
import hashlib
import hmac
import time
from config import CRYPTO_TOKEN

CRYPTO_API = "https://pay.crypt.bot/api"

def create_invoice(amount, description):
    """Создать счет в CryptoBot"""
    url = f"{CRYPTO_API}/createInvoice"
    
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_TOKEN,
        "Content-Type": "application/json"
    }
    
    data = {
        "asset": "USDT",
        "amount": str(amount),
        "description": description,
        "expires_in": 3600  # 1 час
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json().get('result')
    except:
        pass
    
    return None

def check_invoice_status(invoice_id):
    """Проверить статус счета"""
    url = f"{CRYPTO_API}/getInvoices"
    
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_TOKEN
    }
    
    params = {
        "invoice_ids": invoice_id
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            invoices = response.json().get('result', {}).get('items', [])
            if invoices:
                return invoices[0].get('status')
    except:
        pass
    
    return None