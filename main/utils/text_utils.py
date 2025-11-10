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