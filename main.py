import sys
import os
from InquirerPy import inquirer 
from src.deployer.deploy import deploy_token
from src.balance_checker import balance_checker_menu
from src.devwallet_creation import dev_wallet_creation
from src.buywallets_creation import buy_wallets_creation
from src.logger import logger
from src.edit_wallets import edit_wallets_menu
from distributor.distributor import distribute_sol_menu

def clear_console():
    # Кроссплатформенная очистка консоли
    os.system("cls" if os.name == "nt" else "clear")

def print_banner():
    blue = "\033[96m"
    white = "\033[97m"
    reset = "\033[0m"

    banner = rf"""
{blue}███╗   ███╗ █████╗ ████████╗███████╗██╗  ██╗██╗
████╗ ████║██╔══██╗╚══██╔══╝██╔════╝██║  ██║██║
██╔████╔██║███████║   ██║   ███████╗███████║██║██████╗
██║╚██╔╝██║██╔══██║   ██║   ╚════██║██╔══██║██║╚═════╝
██║ ╚═╝ ██║██║  ██║   ██║   ███████║██║  ██║██║
╚═╝     ╚═╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝{reset}
{white}              MatShi- Token Deployer{reset}
    """
    print(banner)

def main_menu():
    while True:
        clear_console()
        print_banner()

        choice = inquirer.select(
            message="Выберите действие:",
            choices=[
                "[+] Start Deploy",
                "[+] DEV-Wallet Creation",
                "[+] Buyers-Wallets Creation",
                "[+] Balance Checker",
                "[+] Edit Wallets",
                "[+] Distribute SOL", #Перед этим создать файл .env, создать и заполнить поле SENDER_PRIVATE_KEY=YourSenderWallet
                "[+] Exit"
            ],
            default="[+] Start Deploy",
        ).execute()

        if choice == "[+] Start Deploy":
            deploy_token()
        elif choice == "[+] DEV-Wallet Creation":
            dev_wallet_creation()
        elif choice == "[+] Buyers-Wallets Creation":
            buy_wallets_creation()
        elif choice == "[+] Balance Checker":
            balance_checker_menu()
        elif choice == "[+] Edit Wallets":
            edit_wallets_menu()
        elif choice == "[+] Distribute SOL":
            distribute_sol_menu()
        elif choice == "[+] Exit":
            logger.info("\nВыход из программы...")
            sys.exit(0)


if __name__ == "__main__":
    main_menu()