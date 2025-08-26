import asyncio
import sqlite3
import requests
import random
import aiohttp
from solders.transaction import VersionedTransaction
from solders.keypair import Keypair
from solders.commitment_config import CommitmentLevel
from solders.rpc.requests import SendVersionedTransaction
from solders.rpc.config import RpcSendTransactionConfig
from src.logger import logger
import base58

RPC_URL = "https://api.mainnet-beta.solana.com"
PUMP_URL = "https://pumpportal.fun/api/trade-local"

BUYER_DB_PATH = "./accounts/buyers/buyer_wallets.db"


# === загрузка buyer-кошельков из sqlite ===
def load_buyer_wallets(group_id: int):
    wallets = []
    try:
        conn = sqlite3.connect(BUYER_DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT number, address, private_key FROM wallets WHERE group_id = ?", (group_id,))
        rows = cur.fetchall()
        conn.close()

        for num, addr, priv in rows:
            try:
                raw = base58.b58decode(priv)
                kp = Keypair.from_bytes(raw)
                wallets.append({"address": str(kp.pubkey()), "keypair": kp})
            except Exception as e:
                logger.error(f"[-] Ошибка при загрузке кошелька {addr}: {e}")
    except Exception as e:
        logger.error(f"[-] Ошибка подключения к базе buyer-кошельков: {e}")
    return wallets


# === проверка готовности токена ===
async def wait_for_token_ready(mint: str, retries: int = 1000, delay: float = 0.5):
    url = RPC_URL

    async with aiohttp.ClientSession() as session:
        for i in range(retries):
            try:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getAccountInfo",
                    "params": [
                        mint,
                        {"encoding": "jsonParsed"}
                    ]
                }

                async with session.post(url, json=payload) as resp:
                    data = await resp.json()
                    value = data.get("result", {}).get("value")

                    if value is not None:
                        logger.info(f"[+] Токен {mint} готов к торговле! AccountInfo получен.")
                        return True

            except Exception as e:
                logger.error(f"[-] Ошибка при проверке токена: {e}")

            logger.warning(f"[*] Токен {mint} ещё не готов, жду {delay} сек...")
            await asyncio.sleep(delay)

    logger.warning("[-] Токен так и не появился, продолжение невозможно")
    return False


# === универсальная функция торговли ===
async def trade_token(wallet: dict, mint: str, action: str):
    public_key = wallet["address"]
    private_key = wallet["keypair"]

    if action == "buy":
        amount_sol = max(0.00101, round(random.uniform(0.00101, 0.00301), 6))
        denominated_in_sol = "true"
        logger.info(f"[{public_key}] Покупка токена на {amount_sol} SOL")
    else:
        amount_sol = "100%"  # продать всё
        denominated_in_sol = "false"
        logger.info(f"[{public_key}] Продажа 100% токенов на buyer-кошельке")

    try:
        response = requests.post(url=PUMP_URL, data={
            "publicKey": public_key,
            "action": action,
            "mint": mint,
            "amount": amount_sol,
            "denominatedInSol": denominated_in_sol,
            "slippage": 30,
            "priorityFee": 0.00001,
            "pool": "pump"
        })

        if response.status_code != 200:
            logger.error(f"[{public_key}] Ошибка запроса к pump.fun: {response.text}")
            return

        try:
            tx = VersionedTransaction(
                VersionedTransaction.from_bytes(response.content).message,
                [private_key]
            )
        except Exception as e:
            logger.error(f"[{public_key}] Ошибка формирования транзакции: {e}")
            return

        commitment = CommitmentLevel.Confirmed
        config = RpcSendTransactionConfig(preflight_commitment=commitment)

        rpc_response = requests.post(
            url=RPC_URL,
            headers={"Content-Type": "application/json"},
            data=SendVersionedTransaction(tx, config).to_json()
        )
        rpc_json = rpc_response.json()

        if "result" in rpc_json and rpc_json["result"]:
            tx_signature = rpc_json["result"]
            logger.info(f"[{public_key}] {action.upper()} tx: https://solscan.io/tx/{tx_signature}")
        else:
            error_msg = rpc_json.get("error", {}).get("message", "Неизвестная ошибка")
            logger.error(f"[{public_key}] Ошибка отправки транзакции: {error_msg}")
            logger.warning(f"[{public_key}] Ответ RPC: {rpc_json}")

    except Exception as e:
        logger.error(f"[{public_key}] Фатальная ошибка при {action}: {e}")


# === продажа токена с dev-кошелька ===
async def signer_sell(dev, mint: str):
    public_key = str(dev.pubkey())
    logger.info(f"[{public_key}] Продажа токена на dev-кошельке")

    response = requests.post(url=PUMP_URL, data={
        "publicKey": public_key,
        "action": "sell",
        "mint": mint,
        "amount": "100%",
        "denominatedInSol": "false",
        "slippage": 30,
        "priorityFee": 0.00001,
        "pool": "pump"
    })

    if response.status_code != 200:
        logger.error(f"[{public_key}] Ошибка запроса: {response.text}")
        return

    try:
        tx = VersionedTransaction(
            VersionedTransaction.from_bytes(response.content).message,
            [dev]
        )
        config = RpcSendTransactionConfig(preflight_commitment=CommitmentLevel.Confirmed)

        rpc_response = requests.post(
            url=RPC_URL,
            headers={"Content-Type": "application/json"},
            data=SendVersionedTransaction(tx, config).to_json()
        )
        tx_signature = rpc_response.json().get("result")
        logger.info(f"[{public_key}] SELL tx: https://solscan.io/tx/{tx_signature}")

    except Exception as e:
        logger.error(f"[{public_key}] Ошибка при обработке транзакции: {e}")


# === массовые операции ===
async def mass_buy(wallets, mint: str):
    tasks = [trade_token(w, mint, "buy") for w in wallets]
    await asyncio.gather(*tasks)

async def mass_sell(wallets, mint: str):
    tasks = [trade_token(w, mint, "sell") for w in wallets]
    await asyncio.gather(*tasks)


# === основной процесс ===
async def start_trading(group_id: int, dev: Keypair, mint: str):
    wallets = load_buyer_wallets(group_id)
    # mint_keypair = mint.pubkey() 
    mint_keypair = mint

    logger.info(f"[+] Загружен dev-кошелёк: {dev.pubkey()}")
    logger.info(f"[+] Загружено {len(wallets)} buyer-кошельков")

    logger.info("\n[+] Проверяю, готов ли токен к трейду...\n")
    ready = await wait_for_token_ready(str(mint_keypair))
    if not ready:
        logger.warning("[-] Ошибка: токен не появился, отмена операций")
        return

    logger.info("\n[+] Запускаем массовую покупку...\n")
    await mass_buy(wallets, str(mint_keypair))
    logger.info("\n[+] Все кошельки купили токен.")

    while True:
        cmd = input("\nВведите 'sell', чтобы продать токен на dev-кошельке: ")
        if cmd.strip().lower() == "sell":
            await signer_sell(dev, str(mint_keypair))
            logger.info("\n[+] Dev-кошелёк продал токен.")
            break
        else:
            logger.warning("[!] Неверная команда. Введите 'sell'.")

    while True:
        cmd = input("\nВведите 'sell', чтобы продать токен на всех кошельках: ")
        if cmd.strip().lower() == "sell":
            await mass_sell(wallets, str(mint_keypair))
            break
        else:
            logger.warning("[!] Неверная команда. Введите 'sell'.")

    logger.info("\n[+] Все кошельки продали токен.")
