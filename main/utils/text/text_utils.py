import re
from datetime import datetime
from typing import Optional
from utils.logger.logger_config import logger


def shorten_name(full_name: str) -> str:
    """
    Сокращает ФИО до "Фамилия И.О.".
    "Пак Анджелика Владимировна" -> "Пак А.В."
    """
    if not full_name:
        return ""

    # Убираем лишние пробелы
    parts = full_name.strip().split()

    if not parts:
        return ""

    if len(parts) < 2:
        return parts[0]

    last_name = parts[0].capitalize()
    initials = ""

    # Берем имя и отчество (максимум 2)
    for part in parts[1:3]:
        initials += f"{part[0].upper()}."

    return f"{last_name} {initials}"


def check_name(full_name: str) -> str:
    """
    Форматирует ФИО для проверки пользователем.
    """
    parts = full_name.strip().split()

    if not parts:
        return "⚠️ Имя не введено"

    last_name = parts[0].capitalize()

    if len(parts) == 1:
        return f"👤 <b>Фамилия:</b> {last_name}\n❓ <b>Имя:</b> Не указано"

    first_name = parts[1].capitalize()

    if len(parts) == 2:
        return f"👤 <b>Фамилия:</b> {last_name}\n👤 <b>Имя:</b> {first_name}"

    # Все остальное считаем отчеством/доп. именами
    middle = " ".join([p.capitalize() for p in parts[2:]])
    return f"👤 <b>Фамилия:</b> {last_name}\n👤 <b>Имя:</b> {first_name}\n👤 <b>Отчество:</b> {middle}"


def validate_phone_number(text: str) -> Optional[str]:
    """
    Очищает и валидирует номер телефона.
    Превращает "8 (777) 123-45-67" -> "+77771234567"
    """
    if not text:
        return None

    text = text.strip()

    # Список стоп-слов, означающих отсутствие номера
    stop_words = {"нет", "не знаю", "отсутствует", "-", "no", "none", "."}
    if text.lower() in stop_words:
        return None

    # Оставляем только цифры и плюс
    clean = re.sub(r"[^\d+]", "", text)

    # 1. Если начинается с 8 и длина 11 (87771234567) -> меняем 8 на +7
    if clean.startswith("8") and len(clean) == 11:
        clean = "+7" + clean[1:]

    # 2. Если просто 10 цифр (7771234567) -> добавляем +7
    elif len(clean) == 10 and not clean.startswith("+"):
        clean = "+7" + clean

    # 3. Финальная проверка regex (Международный формат)
    if re.fullmatch(r"\+?\d{10,15}", clean):
        return clean

    logger.warning(f"⚠️ Невалидный номер телефона: {text}")
    return None


def validate_date(date_str: str) -> Optional[str]:
    """
    Проверяет дату (DD.MM.YYYY).
    Возвращает строку, если дата корректна, иначе None.
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # 1. Проверяем формат (2 цифры . 2 цифры . 4 цифры)
    if not re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", date_str):
        return None

    # 2. Проверяем, существует ли такая дата в календаре
    try:
        # strptime сама проверит високосные года и дни в месяце (30 vs 31)
        valid_date = datetime.strptime(date_str, "%d.%m.%Y")

        # 3. Проверка на адекватность года (не в будущем, не в 19 веке)
        current_year = datetime.now().year
        if not (1950 <= valid_date.year <= current_year):
            logger.warning(f"Дата вне разумного диапазона: {date_str}")
            return None

        return date_str  # Возвращаем исходную строку, если всё ок

    except ValueError:
        # Например, 30.02.2023 вызовет ошибку здесь
        return None