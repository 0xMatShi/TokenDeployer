import logging
import os

# создаём папку logs
os.makedirs("logs", exist_ok=True)

# формат для файла (подробный)
file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

# формат для консоли (кастомный — INFO без префикса)
class ConsoleFormatter(logging.Formatter):
    def format(self, record):
        if record.levelno == logging.INFO:
            return record.getMessage()
        return f"[{record.levelname}] {record.getMessage()}"

# файл — всё подряд
file_handler = logging.FileHandler("logs/app.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(file_formatter)

# консоль — тоже всё, но с кастомным форматтером
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(ConsoleFormatter())

# логгер
logger = logging.getLogger("TokenDeployer")
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)
