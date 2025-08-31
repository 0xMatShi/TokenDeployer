import requests
import json
import os
import base58
import asyncio
import random
import sqlite3
from InquirerPy import inquirer
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.commitment_config import CommitmentLevel
from solders.rpc.requests import SendVersionedTransaction
from solders.rpc.config import RpcSendTransactionConfig
from src.deployer.buysell import start_trading
from src.logger import logger

RPC_URL = "https://api.mainnet-beta.solana.com/"
PUMP_URL = "https://pumpportal.fun/api/trade-local"
DEV_DB_PATH = "./accounts/devs/dev_wallets.db"
DEV_API_DB_PATH = "./accounts/devs/dev_wallets_with_api.db"
BUYER_DB_PATH = "./accounts/buyers/buyer_wallets.db"


def clear_console():
    os.system("cls" if os.name == "nt" else "clear")


# def parse_private_key(key_str: str) -> Keypair:
#     try:
#         raw = base58.b58decode(key_str)
#         return Keypair.from_bytes(raw)
#     except Exception as e:
#         raise ValueError(f"[-] Не удалось распарсить приватный ключ: {e}")


# === DEV CHOICE через SQLite ===
def dev_choice_menu():
    """Выбор dev-кошелька: обычный или с API"""
    choice = inquirer.select(
        message="Выберите источник dev-кошелька:",
        choices=[
            "[+] Dev-кошелёк (обычный)",
            "[+] Dev-кошелёк с API",
        ],
    ).execute()

    if choice == "[+] Dev-кошелёк (обычный)":
        return dev_choice(), "normal"
    elif choice == "[+] Dev-кошелёк с API":
        return dev_choice_api(), "api"


def dev_choice():
    conn = sqlite3.connect(DEV_DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name, address, private_key FROM dev_wallets")
    rows = cur.fetchall()
    conn.close()

    if not rows:
        logger.warning("[-] Нет dev-кошельков в базе.")
        return None

    choices = [f"{row[1]} ({row[2]})" for row in rows]
    choice = inquirer.select(
        message="Выберите dev-кошелёк:",
        choices=choices,
    ).execute()

    wallet = rows[choices.index(choice)]
    _, name, address, privkey = wallet

    kp = Keypair.from_bytes(base58.b58decode(privkey))
    logger.info(f"[+] Выбран dev-кошелек: {name} ({address})")
    return kp

def dev_choice_api():
    """Выбор dev-кошелька с API из dev_wallets_with_api.db"""
    conn = sqlite3.connect(DEV_API_DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name, address, private_key, api_key FROM dev_wallets_with_api")
    rows = cur.fetchall()
    conn.close()

    if not rows:
        logger.warning("[-] Нет dev-кошельков с API в базе.")
        return None

    choices = [f"{row[1]} ({row[2]})" for row in rows]
    choice = inquirer.select(
        message="Выберите dev-кошелёк с API:",
        choices=choices,
    ).execute()

    wallet = rows[choices.index(choice)]
    _, name, address, privkey, api_key = wallet

    kp = Keypair.from_bytes(base58.b58decode(privkey))
    logger.info(f"[+] Выбран dev-кошелек с API: {name} ({address})")
    return {"keypair": kp, "api_key": api_key}


# --- выбор группы buyer-кошельков ---
def buyer_group_choice():
    conn = sqlite3.connect(BUYER_DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM groups")
    rows = cur.fetchall()
    conn.close()

    if not rows:
        logger.warning("[-] Нет доступных групп buyer-кошельков.")
        return None

    choices = [f"{row[1]} (ID: {row[0]})" for row in rows]
    choice = inquirer.select(
        message="Выберите группу buyer-кошельков:",
        choices=choices,
    ).execute()

    group = rows[choices.index(choice)]
    group_id, group_name = group
    logger.info(f"[+] Выбрана группа buyer-кошельков: {group_name} (ID: {group_id})")
    return group_id


def platform_choice():

    logger.info("На какой площадке хотите создать токен?")
    portal_choice = inquirer.select(
        message="Выберите площадку:",
        choices=[
            "[+] Pump.fun",
            "[+] Bonk.fun",
        ],
        default="[+] Pump.fun",
    ).execute()
    
    if portal_choice == "[+] Pump.fun":
        logger.info(f"\n[+] Выбрана площадка: {portal_choice}")
        dev_wallet, dev_type = dev_choice_menu()
        if dev_type == "api":
            signer_keypair = dev_wallet["keypair"]
            api_key = dev_wallet["api_key"]
        else:
            signer_keypair = dev_wallet
            api_key = None
        buyer_keypairs = buyer_group_choice()
        mint_keypair = "9ADoMeegweLhVZNsWopueT1mr8ivdYPmV5e3R4d3pump" 
        asyncio.run(start_trading(buyer_keypairs, signer_keypair, mint_keypair)) #Для тестов покупок/продаж
        # deploy_buy_and_sell_pump()
        input("\nНажмите Enter чтобы вернуться в меню...")
        
    elif portal_choice == "[+] Bonk.fun":
        logger.info(f"\n[+] Выбрана площадка: {portal_choice}")
        deploy_buy_and_sell_bonk()
        input("\nНажмите Enter чтобы вернуться в меню...")
        return


# --- Vanity генератор адресов ---
def generate_vanity_keypair(platform: str):
    """Генерация vanity-адреса с нужным суффиксом"""
    suffix = "pump" if platform.lower() == "pump" else "bonk"
    logger.info(f"Генерация vanity-адреса с суффиксом '{suffix}'...\n")

    attempt = 0
    while True:
        kp = Keypair()
        pubkey_str = str(kp.pubkey())
        attempt += 1
        if pubkey_str.endswith(suffix):
            logger.info(f"[+] Нашёл vanity адрес после {attempt} попыток: {pubkey_str}")
            return kp
        if attempt % 100000 == 0:
            logger.info(f"Попыток: {attempt}... пока без совпадений")


# --- Запрос параметров токена ---
def get_token_metadata():
    while True:
        logger.info("\nВведите данные для токена:\n")
        name = input("1) Name токена: ").strip()
        symbol = input("2) Тикер: ").strip()
        description = input("3) Описание: ").strip()
        twitter = input("4) Twitter (или - если нет): ").strip()
        telegram = input("5) Telegram (или - если нет): ").strip()
        website = input("6) Website (или - если нет): ").strip()

        # Новый пункт — картинка
        while True:
            image_path = input("7) Путь к картинке (или Enter для example.png): ").strip()
            if image_path == "":
                image_path = "./example.png"
            if os.path.isfile(image_path):
                break
            else:
                logger.warning("[-] Файл не найден, попробуйте снова.")

        confirm = input("\nГотовы создать токен? (Yes(y)/No(n)): ").strip().lower()
        if confirm in ["yes", "y"]:
            return {
                'name': name,
                'symbol': symbol,
                'description': description,
                'twitter': "" if twitter == "" else twitter,
                'telegram': "" if telegram == "" else telegram,
                'website': "" if website == "" else website,
                'showName': 'true',
                'image_path': image_path
            }
        else:
            logger.info("\n[-] Заполняем заново...\n")

def deploy_buy_and_sell_pump():
    # 1. Выбираем dev-кошелёк
    dev_wallet, dev_type = dev_choice_menu()
    group_id = buyer_group_choice()

    if not dev_wallet or not group_id:
        logger.warning("[-] Нет доступных кошельков для деплоя.")
        return

    if dev_type == "api":
        signer_keypair = dev_wallet["keypair"]
        api_key = dev_wallet["api_key"]
    else:
        signer_keypair = dev_wallet
        api_key = None

    # 2. Генерация vanity mint-адреса
    mint_keypair = generate_vanity_keypair("pump")

    # 3–10. Получаем метаданные токена
    form_data = get_token_metadata()

    # 11. Читаем картинку
    with open(form_data['image_path'], 'rb') as f:
        file_content = f.read()
    files = {'file': (os.path.basename(form_data['image_path']), file_content, 'image/png')}

    # 12. IPFS upload
    metadata_response = requests.post("https://pump.fun/api/ipfs", data=form_data, files=files)
    metadata_response_json = metadata_response.json()

    # 13. JSON для деплоя
    token_metadata = {
        'name': form_data['name'],
        'symbol': form_data['symbol'],
        'uri': metadata_response_json['metadataUri']
    }

    amount_sol = max(0.0051, round(random.uniform(0.00101, 0.0051), 6))

    response = requests.post(
        PUMP_URL,
        headers={'Content-Type': 'application/json'},
        data=json.dumps({
            'publicKey': str(signer_keypair.pubkey()),
            'action': 'create',
            'tokenMetadata': token_metadata,
            'mint': str(mint_keypair.pubkey()),
            'denominatedInSol': 'true',
            'amount': amount_sol,
            'slippage': 10,
            'priorityFee': 0.00001,
            'pool': 'pump'
        })
    )

    tx = VersionedTransaction(
        VersionedTransaction.from_bytes(response.content).message,
        [mint_keypair, signer_keypair]
    )
    config = RpcSendTransactionConfig(preflight_commitment=CommitmentLevel.Confirmed)

    response = requests.post(
        url=RPC_URL,
        headers={"Content-Type": "application/json"},
        data=SendVersionedTransaction(tx, config).to_json()
    )
    txSignature = response.json()['result']
    logger.info(f"\n[+] Transaction: https://solscan.io/tx/{txSignature}")
    logger.info(f"[+] Token CA: {mint_keypair.pubkey()}")

    # теперь сюда передаём group_id, а не путь
    asyncio.run(start_trading(group_id, signer_keypair, mint_keypair)) # log error

def deploy_buy_and_sell_bonk():
    # 1. Выбираем dev-кошелёк
    dev_wallet, dev_type = dev_choice_menu()
    group_id = buyer_group_choice()

    if not dev_wallet or not group_id:
        logger.warning("[-] Нет доступных кошельков для деплоя.")
        return

    if dev_type == "api":
        signer_keypair = dev_wallet["keypair"]
        api_key = dev_wallet["api_key"]
    else:
        signer_keypair = dev_wallet
        api_key = None


    if not signer_keypair or not group_id:
        logger.warning("[-] Нет доступных кошельков для деплоя.")
        return

    # 2. Генерация mint-адреса
    mint_keypair = generate_vanity_keypair("bonk")  # vanity можно добавить, если надо
    # mint_keypair = Keypair()    

    # 3. Получаем метаданные токена
    form_data = get_token_metadata()

    # 4. Читаем картинку
    with open(form_data['image_path'], 'rb') as f:
        file_content = f.read()

    files = {
        'image': (os.path.basename(form_data['image_path']), file_content, 'image/png')
    }

    # 5. Заливаем картинку на IPFS через Bonk API
    img_response = requests.post(
        "https://nft-storage.letsbonk22.workers.dev/upload/img",
        files=files
    )
    img_uri = img_response.text.strip()

    # 6. Заливаем метаданные
    metadata_response = requests.post(
        "https://nft-storage.letsbonk22.workers.dev/upload/meta",
        headers={'Content-Type': 'application/json'},
        data=json.dumps({
            'createdOn': "https://bonk.fun",
            'description': form_data['description'],
            'image': img_uri,
            'name': form_data['name'],
            'symbol': form_data['symbol'],
            'website': form_data['website']
        })
    )
    metadata_uri = metadata_response.text.strip()

    # 7. Токен метаданные
    token_metadata = {
        'name': form_data['name'],
        'symbol': form_data['symbol'],
        'uri': metadata_uri
    }

    amount_sol = max(0.0051, round(random.uniform(0.00101, 0.0051), 6))

    # 8. Отправляем create-транзакцию
    response = requests.post(
        f"https://pumpportal.fun/api/trade?api-key={api_key if api_key else 'your-api-key-here'}",   # локальный эндпоинт pumpportal
        headers={'Content-Type': 'application/json'},
        data=json.dumps({
            'publicKey': str(signer_keypair.pubkey()),
            'action': 'create',
            'tokenMetadata': token_metadata,
            'mint': str(mint_keypair.pubkey()),
            'denominatedInSol': 'true',
            'amount': amount_sol,
            'slippage': 10,
            'priorityFee': 0.00005,
            'pool': 'bonk'
        })
    )

    if response.status_code != 200:
        logger.error(f"[-] Ошибка при деплое: {response.text}")
        return

    try:
        tx = VersionedTransaction(
            VersionedTransaction.from_bytes(response.content).message,
            [mint_keypair, signer_keypair]
        )

        commitment = CommitmentLevel.Confirmed
        config = RpcSendTransactionConfig(preflight_commitment=commitment)

        rpc_response = requests.post(
            url=RPC_URL,
            headers={"Content-Type": "application/json"},
            data=SendVersionedTransaction(tx, config).to_json()
        )

        rpc_json = rpc_response.json()
        tx_signature = rpc_json.get("result")

        if not tx_signature:
            logger.error(f"[-] Ошибка при отправке транзакции: {rpc_json}")
            return

        logger.info(f"\n[+] Transaction: https://solscan.io/tx/{tx_signature}")
        logger.info(f"[+] Token CA: {mint_keypair.pubkey()}")

        # 9. Запускаем процесс торговли
        asyncio.run(start_trading(group_id, signer_keypair, mint_keypair))

    except Exception as e:
        logger.error(f"[-] Ошибка при формировании или отправке транзакции: {e}")


def deploy_token():
    clear_console()

    logger.info("Выберите действие:")

    choice = inquirer.select(
        message="Выберите действие:",
        choices=[
            "[+] Создать токен",
            "[+] Вернуться в главное меню"
        ],
        default="[+] Создать токен",
    ).execute()

    if choice == "[+] Создать токен":
        platform_choice()
    elif choice == "[+] Вернуться в главное меню":
        return

    