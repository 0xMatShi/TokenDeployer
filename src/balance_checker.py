import os
import sqlite3
from tabulate import tabulate
from InquirerPy import inquirer
from src.logger import logger
import aiohttp
import asyncio

RPC_URL = "https://api.mainnet-beta.solana.com"
DB_PATH = "./accounts/devs/dev_wallets.db"
DB_API_PATH = "./accounts/devs/dev_wallets_with_api.db"
BUYER_DB_PATH = "./accounts/buyers/buyer_wallets.db"


def clear_console():
    os.system("cls" if os.name == "nt" else "clear")

async def get_balance_async(session, pubkey: str) -> float:
    """Асинхронный запрос баланса через Solana RPC"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getBalance",
        "params": [pubkey]
    }
    try:
        async with session.post(RPC_URL, json=payload) as resp:
            data = await resp.json()
            lamports = data.get("result", {}).get("value", 0)
            return lamports / 1_000_000_000
    except Exception as e:
        return f"Ошибка: {e}"


# === DEV WALLET CHECKER ===
def check_dev_wallets_normal():
    if not os.path.exists(DB_PATH):
        logger.warning("\n[-] База dev-кошельков не найдена.")
        input("\nНажмите Enter чтобы продолжить...")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name, address FROM dev_wallets")
    rows = cur.fetchall()
    conn.close()

    if not rows:
        logger.warning("\n[-] В базе нет dev-кошельков.")
        input("\nНажмите Enter чтобы продолжить...")
        return

    choices = [f"{row[1]} ({row[2]})" for row in rows]
    choice = inquirer.select(message="Выберите dev-кошелёк:", choices=choices).execute()

    wallet = rows[choices.index(choice)]
    wallet_id, wallet_name, wallet_address = wallet

    async def fetch():
        async with aiohttp.ClientSession() as session:
            return await get_balance_async(session, wallet_address)

    balance = asyncio.run(fetch())

    logger.info(f"\n[+] Баланс '{wallet_name}' ({wallet_address}): {balance} SOL\n")
    input("\nНажмите Enter чтобы продолжить...")


def check_dev_wallets_api():
    if not os.path.exists(DB_API_PATH):
        logger.warning("\n[-] База dev-кошельков с API не найдена.")
        input("\nНажмите Enter чтобы продолжить...")
        return

    conn = sqlite3.connect(DB_API_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name, address, api_key FROM dev_wallets_with_api")
    rows = cur.fetchall()
    conn.close()

    if not rows:
        logger.warning("\n[-] В базе нет dev-кошельков с API.")
        input("\nНажмите Enter чтобы продолжить...")
        return

    choices = [f"{row[1]} ({row[2]})" for row in rows]
    choice = inquirer.select(message="Выберите dev-кошелёк с API:", choices=choices).execute()

    wallet = rows[choices.index(choice)]
    wallet_id, wallet_name, wallet_address, api_key = wallet

    async def fetch():
        async with aiohttp.ClientSession() as session:
            return await get_balance_async(session, wallet_address)

    balance = asyncio.run(fetch())

    logger.info(f"\n[+] Баланс API dev-кошелька '{wallet_name}' ({wallet_address}): {balance} SOL")

    input("\nНажмите Enter чтобы продолжить...")


# === BUYER WALLETS CHECKER ===
def check_buyer_wallets():
    if not os.path.exists(BUYER_DB_PATH):
        logger.warning("\n[-] База buyer-кошельков не найдена.")
        input("\nНажмите Enter чтобы продолжить...")
        return

    # Получаем список групп
    conn = sqlite3.connect(BUYER_DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM groups")
    groups = cur.fetchall()

    if not groups:
        logger.warning("\n[-] В базе нет групп buyer-кошельков.")
        conn.close()
        input("\nНажмите Enter чтобы продолжить...")
        return

    choices = [f"{row[1]} (ID: {row[0]})" for row in groups]

    choice = inquirer.select(
        message="Выберите группу buyer-кошельков:",
        choices=choices,
    ).execute()

    group = groups[choices.index(choice)]
    group_id, group_name = group

    # Получаем кошельки выбранной группы
    cur.execute("SELECT number, address FROM wallets WHERE group_id = ?", (group_id,))
    wallets = cur.fetchall()
    conn.close()

    if not wallets:
        logger.warning(f"\n[-] В группе '{group_name}' нет кошельков.")
        input("\nНажмите Enter чтобы продолжить...")
        return

    # --- Асинхронно считаем балансы
    async def fetch_all():
        async with aiohttp.ClientSession() as session:
            tasks = [get_balance_async(session, addr) for _, addr in wallets]
            return await asyncio.gather(*tasks)

    balances = asyncio.run(fetch_all())

    # Собираем таблицу
    table = []
    for (num, addr), balance in zip(wallets, balances):
        table.append([num, addr, balance])

    logger.info(f"\n[+] Балансы buyer-кошельков (группа '{group_name}'):\n")
    logger.info(tabulate(table, headers=["№", "Address", "Balance (SOL)"], tablefmt="pretty"))

    input("\nНажмите Enter чтобы продолжить...")


def check_dev_wallets_menu():
    choice = inquirer.select(
        message="Какие dev-кошельки проверить?",
        choices=[
            "[+] Dev-кошельки (обычные)",
            "[+] Dev-кошельки с API",
            "[+] Назад"
        ],
    ).execute()

    if choice == "[+] Назад":
        return
    elif choice == "[+] Dev-кошельки (обычные)":
        check_dev_wallets_normal()
    elif choice == "[+] Dev-кошельки с API":
        check_dev_wallets_api()


# === MAIN BALANCE CHECKER MENU ===
def balance_checker_menu():
    while True:
        clear_console()  # убираем баннер при входе
        choice = inquirer.select(
            message="Меню проверки баланса:",
            choices=[
                "[+] Проверить dev-кошелёк",
                "[+] Проверить buyer-кошельки",
                "[+] Назад в главное меню"
            ],
        ).execute()

        if choice == "[+] Проверить dev-кошелёк":
            check_dev_wallets_menu()
        elif choice == "[+] Проверить buyer-кошельки":
            check_buyer_wallets()
        elif choice == "[+] Назад в главное меню":
            return
