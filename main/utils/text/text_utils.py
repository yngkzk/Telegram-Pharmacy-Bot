import re
from utils.logger.logger_config import logger
from datetime import datetime


def shorten_name(full_name: str) -> str:
    """
    Всегда сокращает ФИО врачей до формата:
    "Фамилия И.О." (если есть отчество) или "Фамилия И." (без отчества).

    Примеры:
        "Пак Анджелика Владимировна" → "Пак А.В."
        "Иванов Иван" → "Иванов И."
        "Ким Сонг" → "Ким С."
        "Ли Мин Хо" → "Ли М.Х."
    """
    # Убираем пробелы по краям и лишние внутри
    text = " ".join(full_name.strip().split())

    parts = text.split()
    if len(parts) < 2:
        # Если передали одно слово, возвращаем как есть
        return text

    last_name = parts[0]
    initials = ""

    # Берём первые буквы имени и отчества (если есть)
    for part in parts[1:3]:  # имя + отчество максимум
        if part:
            initials += f"{part[0]}."

    return f"{last_name} {initials}"

def check_name(full_name: str) -> str:
    """
    Показывает какие именно данные были введены (Имя, Фамилия, Отчество)
    :param full_name: Полное имя, например "George Himself Washington"
    :return: Текст с разбором ФИО
    """
    parts = full_name.strip().split()

    if len(parts) == 1:
        return f"Фамилия: {parts[0]}\nИмя: не указано\nОтчество: не указано"

    elif len(parts) == 2:
        last_name, first_name = parts
        return f"Фамилия: {last_name}\nИмя: {first_name}\nОтчество: отсутствует"

    elif len(parts) >= 3:
        last_name, first_name, *middle = parts
        middle_name = " ".join(middle)
        return f"Фамилия: {last_name}\nИмя: {first_name}\nОтчество (при наличии): {middle_name}"

def validate_phone_number(text: str) -> str | None:
    """
    Проверяет введённый текст на соответствие формату номера телефона.
    Возвращает очищенный номер (например, +77071234567) или None.
    """
    text = text.strip()

    # Разрешаем ввод "нет", "отсутствует" и т.п.
    if text.lower() in {"нет", "не знаю", "—", "-"}:
        logger.info("Пользователь указал, что номера нет.")
        return None

    # Убираем пробелы, тире, скобки
    clean = re.sub(r"[^\d+]", "", text)

    # Проверяем, что остались только цифры (и, возможно, ведущий '+')
    if re.fullmatch(r"\+?\d{7,15}", clean):
        logger.info(f"✅ Введён валидный номер телефона: {clean}")
        return clean

    # Если не похоже на номер — возвращаем None
    logger.warning(f"⚠️ Невалидный номер телефона: {text}")
    return None

def validate_date(date_str: str) -> bool:
    """
    Проверяет корректность даты в формате DD.MM.YYYY.
    """

    # 1. Проверяем формат по регулярке
    if not re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", date_str):
        return False

    day, month, year = map(int, date_str.split("."))

    # 2. Проверяем диапазоны вручную
    if not (1 <= day <= 31):
        return False

    if not (1 <= month <= 12):
        return False

    current_year = datetime.now().year
    if not (1900 <= year <= current_year):
        return False

    # 3. Проверяем реальное существование даты
    try:
        datetime(year, month, day)
    except ValueError:
        return False

    return True