from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from infrastructure.database.db_helper import db_helper
from infrastructure.database.repo.user_repo import UserRepository
from infrastructure.database.repo.report_repo import ReportRepository
from storage.temp_data import TempDataManager

router = Router()


@router.callback_query(F.data == "confirm_yes")
async def final_confirm_report(callback: types.CallbackQuery, state: FSMContext, reports_db: ReportRepository):
    # 1. Получаем реальное имя пользователя из нашей БД
    user_id = callback.from_user.id
    real_name = "Неизвестный"

    async for u_session in db_helper.get_user_session():
        user = await UserRepository(u_session).get_user(user_id)
        if user:
            real_name = user.name  # ТО САМОЕ ИМЯ ИЗ РЕГИСТРАЦИИ

    # 2. Собираем все данные из кэша (которые мы заботливо сохраняли)
    data = await TempDataManager.get_all(state)
    prefix = data.get("prefix")  # 'doc' или 'apt'

    try:
        await reports_db.connect()  # Гарантируем подключение

        if prefix == "doc":
            # --- СОХРАНЯЕМ ОТЧЕТ ПО ВРАЧУ ---
            report_id = await reports_db.save_main_report(
                user=real_name,
                district=data.get("district_name"),
                road=data.get("road_num"),  # Мы сохраняли его как цифру 1-7
                lpu=data.get("lpu_name"),
                doctor_name=data.get("doc_name"),
                doctor_spec=data.get("doc_spec"),
                doctor_number=data.get("doc_num"),
                term=data.get("contract_terms"),  # Убедись, что это поле есть в стейте
                comment=data.get("comms", "")
            )

            # Сохраняем препараты (список имен)
            # Нам нужно вытащить имена из selected_items через prep_map
            selected_ids = data.get("selected_items", [])
            prep_map = data.get("prep_map", {})
            prep_names = [prep_map.get(str(i)) for i in selected_ids]

            await reports_db.save_preps(report_id, prep_names)

        elif prefix == "apt":
            # --- СОХРАНЯЕМ ОТЧЕТ ПО АПТЕКЕ ---
            report_id = await reports_db.save_apothecary_report(
                user=real_name,
                district=data.get("district_name"),
                road=data.get("road_num"),
                lpu=data.get("lpu_name"),  # Для аптеки это имя аптеки
                comment=data.get("comms", "")
            )

            # Сохраняем детали (заявка/остаток)
            final_quantities = data.get("final_quantities", {})
            prep_map = data.get("prep_map", {})

            # Формируем список кортежей (name, req, rem)
            items_to_save = []
            for p_id, vals in final_quantities.items():
                name = prep_map.get(str(p_id))
                items_to_save.append((name, vals['req'], vals['rem']))

            await reports_db.save_apothecary_preps(report_id, items_to_save)

        await callback.message.edit_text(f"✅ Отчёт успешно сохранён!\nСотрудник: <b>{real_name}</b>")
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка сохранения отчета: {e}")
        await callback.answer("❌ Ошибка при сохранении в базу данных", show_alert=True)
    finally:
        pass

    await callback.answer()