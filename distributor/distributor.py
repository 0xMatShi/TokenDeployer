import os
import base58
import sqlite3
from InquirerPy import inquirer
from dotenv import load_dotenv
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
from solders.system_program import TransferParams, transfer
from solders.rpc.requests import SendVersionedTransaction
from solders.rpc.config import RpcSendTransactionConfig
from solders.commitment_config import CommitmentLevel
from solders.hash import Hash
import requests
from src.logger import logger

# === Конфиги ===
RPC_URL = "https://api.mainnet-beta.solana.com"
BUYER_DB_PATH = "./accounts/buyers/buyer_wallets.db"

# Загружаем .env
load_dotenv()
SENDER_PRIVKEY = os.getenv("SENDER_PRIVATE_KEY")  # приватник в base58 из .env

if not SENDER_PRIVKEY:
    raise ValueError("[-] В .env не найден SENDER_PRIVATE_KEY")

sender = Keypair.from_base58_string(SENDER_PRIVKEY)

def _make_recent_blockhash(hash_str: str) -> Hash:
    """
    Попытки безопасно конвертировать блокхэш-строку (base58) в solders.hash.Hash,
    поддерживая несколько возможных API классов Hash.
    """
    raw = base58.b58decode(hash_str)
    # Попробуем разные фабрики, если они есть в версии solders
    if hasattr(Hash, "from_string"):
        try:
            return Hash.from_string(hash_str)
        except Exception:
            pass
    if hasattr(Hash, "from_bytes"):
        try:
            return Hash.from_bytes(raw)
        except Exception:   
            pass
    # fallback — конструктор, если принимает bytes
    try:
        return Hash(raw)
    except Exception as e:
        raise RuntimeError(f"Не удалось создать Hash из blockhash: {e}")


def get_buyer_wallets(group_name: str = None):
    """Достаём buyer-кошельки (всей базы или конкретной группы)"""
    conn = sqlite3.connect(BUYER_DB_PATH)
    cur = conn.cursor()

    if group_name:
        cur.execute("""
            SELECT wallets.address 
            FROM wallets
            JOIN groups ON wallets.group_id = groups.id
            WHERE groups.name = ?
        """, (group_name,))
    else:
        cur.execute("SELECT address FROM wallets")

    wallets = [row[0] for row in cur.fetchall()]
    conn.close()
    return wallets


def send_sol(sender: Keypair, recipient: str, amount_sol: float) -> bool:
    """
    Отправляет amount_sol SOL с Keypair sender на адрес recipient (строка).
    Возвращает True при успехе, False при ошибке.
    """
    lamports = int(amount_sol * 1_000_000_000)
    try:
        # 1) Получаем latest blockhash
        resp = requests.post(RPC_URL, json={"jsonrpc":"2.0","id":1,"method":"getLatestBlockhash"})
        resp.raise_for_status()
        j = resp.json()
        blockhash_str = j["result"]["value"]["blockhash"]
    except Exception as e:
        logger.error(f"[!] Не удалось получить latest blockhash: {e}")
        return False

    try:
        recent_blockhash = _make_recent_blockhash(blockhash_str)
    except Exception as e:
        logger.error(f"[!] Ошибка при конвертации blockhash -> Hash: {e}")
        return False

    try:
        # 2) Инструкция system transfer
        ix = transfer(
            TransferParams(
                from_pubkey=sender.pubkey(),
                to_pubkey=Pubkey.from_string(recipient),
                lamports=lamports
            )
        )

        # 3) Сформировать MessageV0
        msg = MessageV0.try_compile(
            payer=sender.pubkey(),
            instructions=[ix],
            recent_blockhash=recent_blockhash,
            address_lookup_table_accounts=[]
        )

        # 4) Подписать VersionedTransaction
        tx = VersionedTransaction(msg, [sender])

        # 5) Отправить в RPC
        config = RpcSendTransactionConfig(preflight_commitment=CommitmentLevel.Confirmed)
        rpc_resp = requests.post(
            RPC_URL,
            headers={"Content-Type": "application/json"},
            data=SendVersionedTransaction(tx, config).to_json()
        )
        rpc_json = rpc_resp.json()

        if "result" in rpc_json and rpc_json["result"]:
            logger.info(f"[+] SEND SOL tx: https://solscan.io/tx/{rpc_json['result']}")
            return True
        else:
            err = rpc_json.get("error", rpc_json)
            logger.error(f"[!] Ошибка отправки: {err}")
            return False

    except Exception as e:
        logger.error(f"[!] Ошибка при отправке: {e}")
        return False

def get_balance(pubkey: str) -> float:
    """Возвращает баланс кошелька в SOL (float)"""
    try:
        resp = requests.post(RPC_URL, json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [pubkey]
        })
        resp.raise_for_status()
        data = resp.json()
        lamports = data.get("result", {}).get("value", 0)
        return lamports / 1_000_000_000
    except Exception as e:
        logger.error(f"[!] Ошибка при получении баланса {pubkey}: {e}")
        return 0.0

def distribute_sol(amounts: list[float], group_name: str = None, min_balance: float = 0.009):
    """
    Раскидываем SOL по списку buyer-кошельков.
    min_balance — если у кошелька есть SOL больше этого значения, пропускаем перевод.
    """
    wallets = get_buyer_wallets(group_name)

    if not wallets:
        logger.warning("[-] Нет buyer-кошельков для распределения")
        return

    if len(amounts) != len(wallets):
        logger.error("[-] Кол-во сумм не совпадает с кол-вом кошельков")
        return

    logger.info(f"[+] Начинаем распределение на {len(wallets)} кошельков")

    for recipient, amount in zip(wallets, amounts):
        balance = get_balance(recipient)
        if balance > min_balance:
            logger.info(f"[~] Пропускаем {recipient}, баланс {balance:.6f} SOL (порог {min_balance} SOL)")
            continue

        send_sol(sender, recipient, amount)


def distribute_sol_menu():
    # ввод суммы
    amount_str = input("Введите сумму (в SOL), которую должен получить каждый buyer-кошелёк: ").strip()
    try:
        amount = float(amount_str)
    except ValueError:
        logger.error("[-] Неверная сумма")
        input("\nНажмите Enter чтобы вернуться...")
        return

    # выбор группы
    import sqlite3
    BUYER_DB_PATH = "./accounts/buyers/buyer_wallets.db"

    if not os.path.exists(BUYER_DB_PATH):
        logger.error("[-] База buyer-кошельков не найдена")
        input("\nНажмите Enter чтобы вернуться...")
        return

    conn = sqlite3.connect(BUYER_DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM groups")
    groups = cur.fetchall()
    conn.close()

    if not groups:
        logger.warning("[-] Нет групп buyer-кошельков")
        input("\nНажмите Enter чтобы вернуться...")
        return

    choices = [f"{row[1]} (ID {row[0]})" for row in groups]
    choice = inquirer.select(
        message="Выберите группу buyer-кошельков:",
        choices=choices,
    ).execute()

    group = groups[choices.index(choice)]
    group_id, group_name = group

    # достаём кошельки
    wallets = get_buyer_wallets(group_name)
    if not wallets:
        logger.warning("[-] В группе нет кошельков")
        input("\nНажмите Enter чтобы вернуться...")
        return

    # формируем список сумм (каждому по одинаковой сумме)
    amounts = [amount] * len(wallets)

    logger.info(f"\n[+] Распределяем по {amount} SOL каждому из {len(wallets)} кошельков группы '{group_name}'\n")
    distribute_sol(amounts, group_name)

    input("\nНажмите Enter чтобы вернуться...")
