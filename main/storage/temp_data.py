from aiogram.fsm.context import FSMContext
from typing import Any, Dict, Optional, Tuple, Union


class TempDataManager:
    """
    Управление временными данными пользователя в FSMContext.
    Оптимизирован для минимизации чтений/записей в Redis/Memory.
    """

    # ============================================================
    # 📦 CORE DATA METHODS
    # ============================================================

    @staticmethod
    async def set(state: FSMContext, key: str, value: Any) -> None:
        """Сохраняет одно значение."""
        await state.update_data({key: value})

    @staticmethod
    async def update(state: FSMContext, data: Dict[str, Any]) -> None:
        """Сохраняет сразу словарь значений."""
        await state.update_data(data)

    @staticmethod
    async def get(state: FSMContext, key: str, default: Optional[Any] = None) -> Any:
        """Возвращает одно значение."""
        data = await state.get_data()
        return data.get(key, default)

    @staticmethod
    async def get_many(state: FSMContext, *keys: str) -> Tuple[Any, ...]:
        """
        Возвращает кортеж значений.
        Пример: name, age = await TempDataManager.get_many(state, "name", "age")
        """
        data = await state.get_data()
        return tuple(data.get(k) for k in keys)

    @staticmethod
    async def get_all(state: FSMContext) -> Dict[str, Any]:
        """
        🔥 NEW: Возвращает ВСЕ данные состояния.
        Нужен для генерации итогового отчета.
        """
        return await state.get_data()

    @staticmethod
    async def remove(state: FSMContext, *keys: str) -> None:
        """Удаляет указанные ключи из состояния."""
        data = await state.get_data()
        changed = False
        for k in keys:
            if k in data:
                data.pop(k)
                changed = True

        # Перезаписываем только если были изменения
        if changed:
            await state.set_data(data)

    @staticmethod
    async def clear(state: FSMContext) -> None:
        """Полностью очищает FSM."""
        await state.clear()

    # ============================================================
    # 🔘 BUTTON MEMORY (Для сохранения текста нажатых кнопок)
    # ============================================================

    @staticmethod
    async def save_button(state: FSMContext, callback_data: str, text: str) -> None:
        """
        Сохраняет маппинг callback -> text.
        Оптимизировано: не перезаписывает весь стейт.
        """
        data = await state.get_data()
        buttons: Dict[str, str] = data.get("button_memory", {})

        # Обновляем локально
        buttons[callback_data] = text

        # Записываем только обновленный словарь кнопок
        await state.update_data(button_memory=buttons)

    @staticmethod
    async def get_button_name(state: FSMContext, callback_data: str) -> Optional[str]:
        data = await state.get_data()
        buttons = data.get("button_memory", {})
        return buttons.get(callback_data)

    @staticmethod
    async def clear_buttons(state: FSMContext) -> None:
        """Быстрая очистка памяти кнопок."""
        await state.update_data(button_memory={})

    # ============================================================
    # 🧩 EXTRA DATA (Для сложных структур)
    # ============================================================

    @staticmethod
    async def save_extra(state: FSMContext, callback: str, **kwargs) -> None:
        """Сохраняет доп. данные для конкретного callback."""
        data = await state.get_data()
        extra = data.get("extra", {})
        extra[callback] = kwargs
        await state.update_data(extra=extra)

    @staticmethod
    async def get_extra(state: FSMContext, callback: str) -> Optional[Dict[str, Any]]:
        data = await state.get_data()
        extra = data.get("extra", {})
        return extra.get(callback)