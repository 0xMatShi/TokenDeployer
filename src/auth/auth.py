import os
import hashlib
from getpass import getpass

PASS_DIR = os.path.join(os.path.dirname(__file__), "auth_pass")  # src/auth
PASS_FILE = os.path.join(PASS_DIR, ".soft_pass")

def _hash_password(password: str) -> str:
    """Хэшируем пароль SHA256 (для хранения)"""
    return hashlib.sha256(password.encode()).hexdigest()

def setup_password():
    """Первичная установка пароля"""
    os.makedirs(PASS_DIR, exist_ok=True)

    while True:
        pwd1 = getpass("Придумайте пароль для входа в софт: ").strip()
        pwd2 = getpass("Повторите пароль: ").strip()
        if pwd1 != pwd2:
            print("Пароли не совпадают, попробуйте ещё раз.\n")
            continue
        if len(pwd1) < 6:
            print("Пароль слишком короткий, минимум 6 символов.\n")
            continue
        hashed = _hash_password(pwd1)
        with open(PASS_FILE, "w") as f:
            f.write(hashed)
        print("Пароль установлен. Перезапустите софт.\n")
        exit(0)

def check_password():
    """Проверка пароля при запуске"""
    if not os.path.exists(PASS_FILE):
        setup_password()
    else:
        with open(PASS_FILE, "r") as f:
            saved_hash = f.read().strip()

        for _ in range(3):  # 3 попытки
            pwd = getpass("Введите пароль для входа: ").strip()
            if _hash_password(pwd) == saved_hash:
                print("Доступ разрешён ✅\n")
                return True
            else:
                print("Неверный пароль ❌")

        print("Слишком много неверных попыток. Выход.")
        exit(1)
