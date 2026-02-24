from aiogram.fsm.context import FSMContext
from typing import Any, Optional, Dict


class TempDataManager:
    """
    Класс-обертка для удобной работы с FSMContext (временным хранилищем).
    """

    @staticmethod
    async def set(state: FSMContext, key: str, value: Any):
        """Сохранить значение по ключу"""
        await state.update_data({key: value})

    @staticmethod
    async def get(state: FSMContext, key: str, default: Any = None) -> Any:
        """Получить значение по ключу"""
        data = await state.get_data()
        return data.get(key, default)

    @staticmethod
    async def get_all(state: FSMContext) -> Dict[str, Any]:
        """Получить все данные"""
        return await state.get_data()

    @staticmethod
    async def get_many(state: FSMContext, *keys) -> list:
        """Получить сразу несколько значений"""
        data = await state.get_data()
        return [data.get(key) for key in keys]

    @staticmethod
    async def remove(state: FSMContext, *keys):
        """Удалить ключи из состояния"""
        data = await state.get_data()
        new_data = {k: v for k, v in data.items() if k not in keys}
        await state.set_data(new_data)

    # ==========================================
    # 🔘 ЛОГИКА ДЛЯ ИМЕН КНОПОК (ЭТОГО НЕ БЫЛО)
    # ==========================================

    @staticmethod
    async def save_button(state: FSMContext, callback_data: str, text: str):
        """Сохраняет текст кнопки, привязанный к ее callback_data"""
        data = await state.get_data()
        # Используем отдельный словарь внутри state, чтобы не мусорить
        buttons = data.get("buttons_map", {})
        buttons[callback_data] = text
        await state.update_data(buttons_map=buttons)

    @staticmethod
    async def get_button_name(state: FSMContext, callback_data: str) -> Optional[str]:
        """Возвращает текст кнопки по callback_data"""
        data = await state.get_data()
        buttons = data.get("buttons_map", {})
        return buttons.get(callback_data)

    # ==========================================
    # 🔗 ЛОГИКА ДЛЯ URL (ДОП. ДАННЫЕ)
    # ==========================================

    @staticmethod
    async def get_extra(state: FSMContext, key: str) -> Optional[dict]:
        """Получает доп. данные (например, URL)"""
        data = await state.get_data()
        # Мы сохраняли URL как "url_prefix_id", попробуем найти
        # Это упрощенная логика, можно адаптировать под твои нужды
        url_key = f"url_{key}"
        url = data.get(url_key)
        if url:
            return {'url': url}
        return None