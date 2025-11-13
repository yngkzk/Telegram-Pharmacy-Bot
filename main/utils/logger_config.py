import logging
from logging.handlers import RotatingFileHandler
import os


def setup_logger(name: str = "bot", log_dir: str = "logs", max_bytes: int = 2_000_000, backup_count: int = 5):
    """Создает и настраивает логгер для проекта"""
    # Папка для логов
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{name}.log")

    # Формат логов
    log_format = "%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"

    # Настройка логгера
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Консольный вывод
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))

    # Логи в файл (с ротацией)
    file_handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(log_format))

    # Добавляем хендлеры
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger

logger = setup_logger()