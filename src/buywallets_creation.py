import os
import sqlite3
from solders.keypair import Keypair
from src.logger import logger
from datetime import datetime

DB_PATH = "./accounts/buyers/buyer_wallets.db"

def init_db():
    os.makedirs("./accounts/buyers", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS wallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            number INTEGER,
            address TEXT,
            private_key TEXT,
            FOREIGN KEY(group_id) REFERENCES groups(id)
        )
    """)
    conn.commit()
    conn.close()

def buy_wallets_creation():
    init_db()

    group_name = input("Введите название для группы buyer-кошельков (Enter, если передумали): ").strip()
    if group_name == "":
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Создаём запись о группе
    created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cur.execute("INSERT INTO groups (name, created_at) VALUES (?, ?)", (group_name, created_at))
        group_id = cur.lastrowid
    except sqlite3.IntegrityError:
        logger.error(f"\n[-] Группа '{group_name}' уже существует.")
        conn.close()
        return

    # Создаём 20 buyer-кошельков
    wallets = []
    for i in range(int(input("Сколько buyer-кошельков создать? (по умолчанию 20): ")) or 20):
        kp = Keypair()
        address = str(kp.pubkey())
        privkey = kp.__str__()  # base58 приватник
        wallets.append((group_id, i + 1, address, privkey))

    cur.executemany("INSERT INTO wallets (group_id, number, address, private_key) VALUES (?, ?, ?, ?)", wallets)
    conn.commit()
    conn.close()

    logger.info(f"\n[+] Создано 20 buyer-кошельков в группе '{group_name}'.")
    for w in wallets:
        logger.info(f"{w[1]}) {w[2]}")

    return
