from aiogram.fsm.context import FSMContext
from typing import Any, Dict, Optional


class TempDataManager:
    """Управление временными данными пользователя в FSMContext."""

    # === Основные методы ===
    @staticmethod
    async def set(state: FSMContext, key: str, value: Any) -> None:
        """
        Сохраняет временное значение по ключу.
        Пример:
            await TempDataManager.set(state, "lpu", "Поликлиника №7")
        """
        await state.update_data({key: value})

    @staticmethod
    async def get(state: FSMContext, key: str, default: Optional[Any] = None) -> Any:
        """
        Возвращает временное значение по ключу.
        Пример:
            lpu = await TempDataManager.get(state, "lpu")
        """
        data = await state.get_data()
        return data.get(key, default)

    @staticmethod
    async def get_many(state: FSMContext, *keys: str) -> tuple:
        """
        Возвращает несколько значений сразу.
        Пример:
            district, road, lpu = await TempDataManager.get_many(state, "district", "road", "lpu")
        """
        data = await state.get_data()
        return tuple(data.get(k) for k in keys)

    @staticmethod
    async def remove(state: FSMContext, *keys: str) -> None:
        data = await state.get_data()
        for k in keys:
            data.pop(k, None)
        await state.set_data(data)

    @staticmethod
    async def clear(state: FSMContext) -> None:
        """
        Полностью очищает временные данные.
        """
        await state.clear()

    # === Память кнопок ===
    @staticmethod
    async def save_button(state: FSMContext, callback_data: str, text: str) -> None:
        """
        Сохраняет текст кнопки по callback_data.
        """
        data = await state.get_data()
        buttons: Dict[str, str] = data.get("button_memory", {})
        buttons[callback_data] = text
        await state.update_data({"button_memory": buttons})

    @staticmethod
    async def get_button_name(state: FSMContext, callback_data: str) -> Optional[str]:
        """
        Возвращает текст кнопки по callback_data.
        """
        data = await state.get_data()
        buttons: Dict[str, str] = data.get("button_memory", {})
        return buttons.get(callback_data)

    @staticmethod
    async def clear_buttons(state: FSMContext) -> None:
        """
        Полностью очищает память кнопок.
        """
        data = await state.get_data()
        data["button_memory"] = {}
        await state.update_data(data)

    @staticmethod
    async def save_extra(state: FSMContext, callback: str, **kwargs) -> None:
        data = await state.get_data()
        extra = data.get("extra", {})
        extra[callback] = kwargs
        await state.update_data(extra=extra)

    @staticmethod
    async def get_extra(state: FSMContext, callback: str) -> None:
        data = await state.get_data()
        extra = data.get("extra", {})
        return extra.get(callback)