import os
import sqlite3
from InquirerPy import inquirer
from src.logger import logger

DEV_DB_PATH = "./accounts/devs/dev_wallets.db"
DEV_API_DB_PATH = "./accounts/devs/dev_wallets_with_api.db"
BUYER_DB_PATH = "./accounts/buyers/buyer_wallets.db"


def clear_console():
    os.system("cls" if os.name == "nt" else "clear")


# ===== Общие функции для работы с базами =====
def select_wallet(db_path, table_name, extra_fields=None):
    """Выбор кошелька из таблицы"""

    # --- проверка, что база существует ---
    if not os.path.exists(db_path):
        if db_path == DEV_DB_PATH:
            logger.warning(f"[-] База dev-кошельков не найдена.")
        else:
            logger.warning(f"[-] База dev-кошельков с API не найдена.")
        input("\nНажмите Enter чтобы продолжить...")
        return None

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    fields = ["id", "name", "address", "private_key"]
    if extra_fields:
        fields += extra_fields

    try:
        cur.execute(f"SELECT {','.join(fields)} FROM {table_name}")
        rows = cur.fetchall()
    except sqlite3.OperationalError:
        logger.warning(f"[-] Таблица {table_name} в базе {os.path.basename(db_path)} не найдена.")
        conn.close()
        input("\nНажмите Enter чтобы продолжить...")
        return None

    conn.close()

    if not rows:
        logger.warning("[-] Нет кошельков в базе")
        input("\nНажмите Enter чтобы продолжить...")
        return None

    choices = [f"{row[1]} ({row[2]})" for row in rows]
    choice = inquirer.select(
        message="Выберите кошелёк:",
        choices=choices,
    ).execute()

    return rows[choices.index(choice)]


def edit_wallet(db_path, table_name, wallet, with_api=False):
    """Меню редактирования кошелька"""
    while True:
        clear_console()
        print("\n[+] Информация о кошельке:\n")
        print(f"Имя: {wallet[1]}")
        print(f"Публичный ключ: {wallet[2]}")
        print(f"Приватный ключ: {wallet[3]}")
        if with_api:
            print(f"API Key: {wallet[4]}")

        choice = inquirer.select(
            message="Действие:",
            choices=[
                "[+] Изменить название",
                "[+] Удалить кошелек",
                "[+] Выйти в меню редактирования"
            ],
        ).execute()

        if choice == "[+] Изменить название":
            new_name = input("Введите новое название: ").strip()
            if new_name:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute(f"UPDATE {table_name} SET name = ? WHERE id = ?", (new_name, wallet[0]))
                conn.commit()
                conn.close()
                wallet = (wallet[0], new_name, *wallet[2:])
                logger.info("[+] Название обновлено")
                input("\nEnter чтобы продолжить...")

        elif choice == "[+] Удалить кошелек":
            confirm = input("Вы уверены? (y/n): ").strip().lower()
            if confirm == "y":
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute(f"DELETE FROM {table_name} WHERE id = ?", (wallet[0],))
                conn.commit()
                conn.close()
                logger.warning("[!] Кошелёк удалён")
                input("\nEnter чтобы продолжить...")
                return  # выходим из меню, кошелька больше нет

        elif choice == "[+] Выйти в меню редактирования":
            return

def edit_buyer_wallets(group_id, group_name):
    """Меню редактирования кошельков внутри группы"""
    conn = sqlite3.connect(BUYER_DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, number, address, private_key FROM wallets WHERE group_id = ?", (group_id,))
    wallets = cur.fetchall()
    conn.close()

    if not wallets:
        logger.warning("[-] В группе нет кошельков")
        input("\nEnter чтобы продолжить...")
        return

    choices = [f"{row[1]} ({row[2]})" for row in wallets]
    choice = inquirer.select(
        message=f"Выберите buyer-кошелёк из группы '{group_name}':",
        choices=choices,
    ).execute()

    wallet = wallets[choices.index(choice)]
    wallet_id, number, address, private = wallet

    while True:
        clear_console()
        print("\n[+] Информация о buyer-кошельке:\n")
        print(f"Номер: {number}")
        print(f"Публичный ключ: {address}")
        print(f"Приватный ключ: {private}")

        choice = inquirer.select(
            message="Действие:",
            choices=[
                "[+] Удалить кошелек",
                "[+] Выйти в меню группы"
            ],
        ).execute()

        if choice == "[+] Удалить кошелек":
            confirm = input("Вы уверены? (y/n): ").strip().lower()
            if confirm == "y":
                conn = sqlite3.connect(BUYER_DB_PATH)
                cur = conn.cursor()
                cur.execute("DELETE FROM wallets WHERE id = ?", (wallet_id,))
                conn.commit()
                conn.close()
                logger.warning("[!] Buyer-кошелёк удалён")
                input("\nEnter чтобы продолжить...")
                return  # назад в список кошельков

        elif choice == "[+] Выйти в меню группы":
            return

# ===== Меню для DEV =====
def dev_wallets_menu():
    choice = inquirer.select(
        message="Выберите тип dev-кошельков:",
        choices=[
            "[+] Dev-кошельки (без API)",
            "[+] Dev-кошельки (с API)",
            "[+] Назад"
        ],
    ).execute()

    if choice == "[+] Dev-кошельки (без API)":
        wallet = select_wallet(DEV_DB_PATH, "dev_wallets")
        if wallet:
            edit_wallet(DEV_DB_PATH, "dev_wallets", wallet)

    elif choice == "[+] Dev-кошельки (с API)":
        wallet = select_wallet(DEV_API_DB_PATH, "dev_wallets_with_api", extra_fields=["api_key"])
        if wallet:
            edit_wallet(DEV_API_DB_PATH, "dev_wallets_with_api", wallet, with_api=True)


# ===== Меню для BUYER =====
def buyer_group_menu(group_id, group_name):
    """Меню управления группой buyer-кошельков"""
    while True:
        clear_console()
        print(f"\n[+] Группа buyer-кошельков: {group_name}\n")

        choice = inquirer.select(
            message="Действие с группой:",
            choices=[
                "[+] Изменить название группы",
                "[+] Удалить группу",
                "[+] Посмотреть кошельки группы",
                "[+] Выйти в меню редактирования"
            ],
        ).execute()

        if choice == "[+] Изменить название группы":
            new_name = input("Введите новое название группы: ").strip()
            if new_name:
                conn = sqlite3.connect(BUYER_DB_PATH)
                cur = conn.cursor()
                cur.execute("UPDATE groups SET name = ? WHERE id = ?", (new_name, group_id))
                conn.commit()
                conn.close()
                group_name = new_name
                logger.info("[+] Название группы обновлено")
                input("\nEnter чтобы продолжить...")

        elif choice == "[+] Удалить группу":
            confirm = input(f"Вы уверены, что хотите удалить всю группу '{group_name}' и все её кошельки? (y/n): ").strip().lower()
            if confirm == "y":
                conn = sqlite3.connect(BUYER_DB_PATH)
                cur = conn.cursor()
                cur.execute("DELETE FROM wallets WHERE group_id = ?", (group_id,))
                cur.execute("DELETE FROM groups WHERE id = ?", (group_id,))
                conn.commit()
                conn.close()
                logger.warning(f"[!] Группа '{group_name}' и все её кошельки удалены")
                input("\nEnter чтобы продолжить...")
                return  # выходим, группы больше нет

        elif choice == "[+] Посмотреть кошельки группы":
            edit_buyer_wallets(group_id, group_name)

        elif choice == "[+] Выйти в меню редактирования":
            return


def buyer_wallets_menu():
    if not os.path.exists(BUYER_DB_PATH):
        logger.warning("\n[-] База buyer-кошельков не найдена.")
        input("\nНажмите Enter чтобы продолжить...")
        return

    conn = sqlite3.connect(BUYER_DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM groups")
    groups = cur.fetchall()
    conn.close()

    if not groups:
        logger.warning("[-] Нет групп buyer-кошельков")
        input("\nEnter чтобы продолжить...")
        return

    choices = [f"{row[1]} (ID {row[0]})" for row in groups]
    choice = inquirer.select(
        message="Выберите группу:",
        choices=choices,
    ).execute()

    group = groups[choices.index(choice)]
    group_id, group_name = group

    # Переходим в меню группы
    buyer_group_menu(group_id, group_name)


# ===== Главное меню =====
def edit_wallets_menu():
    while True:
        clear_console()
        choice = inquirer.select(
            message="Меню редактирования кошельков:",
            choices=[
                "[+] Dev-кошельки",
                "[+] Buyer-кошельки",
                "[+] Вернуться в главное меню"
            ],
        ).execute()

        if choice == "[+] Dev-кошельки":
            dev_wallets_menu()
        elif choice == "[+] Buyer-кошельки":
            buyer_wallets_menu()
        elif choice == "[+] Вернуться в главное меню":
            return
