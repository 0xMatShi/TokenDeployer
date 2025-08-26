import os
import sqlite3
import requests
from InquirerPy import inquirer
from solders.keypair import Keypair
from src.logger import logger

DB_PATH = "./accounts/devs/dev_wallets.db"
DB_API_PATH = "./accounts/devs/dev_wallets_with_api.db"

def init_db():
    """Создаём таблицы для dev-кошельков (обычных и с API), если их нет"""

    # --- Обычные dev-кошельки ---
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dev_wallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            private_key TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

    # --- Dev-кошельки с API ---
    os.makedirs(os.path.dirname(DB_API_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_API_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dev_wallets_with_api (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            private_key TEXT NOT NULL,
            api_key TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_wallet(name: str, pubkey: str, privkey: str):
    """Сохраняем кошелёк в базу"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO dev_wallets (name, address, private_key) VALUES (?, ?, ?)",
        (name, pubkey, privkey)
    )
    conn.commit()
    conn.close()


def save_wallet_with_api(name: str, pubkey: str, privkey: str, api_key: str):
    conn = sqlite3.connect(DB_API_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO dev_wallets_with_api (name, address, private_key, api_key) VALUES (?, ?, ?, ?)",
        (name, pubkey, privkey, api_key)
    )
    conn.commit()
    conn.close()


def dev_wallet_creation():
    init_db()

    choice = inquirer.select(
        message="Что создать?",
        choices=[
            "[+] Обычный dev-кошелёк",
            "[+] Dev-кошелёк с API (pumpportal.fun)",
            "[+] Отмена"
        ],
    ).execute()

    if choice == "[+] Отмена":
        logger.warning("Создание отменено")
        return

    dev = input("Введите название для кошелька: ").strip()
    if dev == "":
        logger.warning("Создание dev-кошелька отменено")
        return

    if choice == "[+] Обычный dev-кошелёк":
        signer_keypair = Keypair()
        pubkey = str(signer_keypair.pubkey())
        privkey = signer_keypair.__str__()  # base58 приватник

        save_wallet(dev, pubkey, privkey)
        logger.info(f"\n[+] Создан обычный dev-кошелёк '{dev}' ({pubkey})")

    elif choice == "[+] Dev-кошелёк с API (pumpportal.fun)":
        response = requests.get("https://pumpportal.fun/api/create-wallet")
        data = response.json()

        pubkey = data.get("walletPublicKey")
        privkey = data.get("privateKey")
        api_key = data.get("apiKey")

        if not (pubkey and privkey and api_key):
            logger.error("[-] Ошибка: не удалось получить кошелёк с API")
            input("\nНажмите Enter чтобы продолжить...")
            return

        save_wallet_with_api(dev, pubkey, privkey, api_key)
        logger.info(f"\n[+] Создан dev-кошелёк с API '{dev}' ({pubkey})")
        logger.warning(f"[!] API-ключ сохранён в {DB_API_PATH}, храните файл в безопасности!")
