from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

from infrastructure.database.db_helper import db_helper
from infrastructure.database.repo.user_repo import UserRepository
from infrastructure.database.repo.report_repo import ReportRepository
from storage.temp_data import TempDataManager
from states.add.prescription_state import PrescriptionFSM

router = Router()

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

from infrastructure.database.db_helper import db_helper
from infrastructure.database.repo.user_repo import UserRepository
from infrastructure.database.repo.report_repo import ReportRepository
from infrastructure.database.repo.pharmacy_repo import PharmacyRepository  # <--- НУЖНО ДЛЯ СПИСКА ВРАЧЕЙ
from storage.temp_data import TempDataManager
from states.add.prescription_state import PrescriptionFSM
from keyboard.inline.inline_buttons import get_doctors_inline  # <--- НУЖНО ДЛЯ КЛАВИАТУРЫ

router = Router()


@router.callback_query(F.data == "confirm_yes", PrescriptionFSM.confirmation)
async def final_save_report(
        callback: types.CallbackQuery,
        state: FSMContext,
        reports_db: ReportRepository
):
    """
    Финальное сохранение отчета и возврат в меню ЛПУ.
    """
    # 1. Получаем реальное имя сотрудника
    user_id = callback.from_user.id
    real_name = callback.from_user.full_name

    async for u_session in db_helper.get_user_session():
        user = await UserRepository(u_session).get_user(user_id)
        if user and user.user_name:
            real_name = user.user_name

    # 2. Достаем все данные
    data = await TempDataManager.get_all(state)

    district_name = data.get("district_name")
    road_num = data.get("road_num")
    lpu_name = data.get("lpu_name")
    lpu_id = data.get("lpu_id")  # <--- ВАЖНО: Нам нужен ID чтобы вернуть меню
    doc_name = data.get("doc_name")
    doc_spec = data.get("doc_spec")
    doc_num = data.get("doc_num")
    terms = data.get("contract_terms", "Нет условий")
    comment = data.get("comms", "")

    # Проверка на целостность данных
    if not district_name or not road_num:
        await callback.answer("Ошибка: Данные локации потеряны. Начните заново.", show_alert=True)
        await state.clear()
        return

    # Форматируем маршрут
    road_formatted = f"Маршрут {road_num}" if road_num else "Не указан"

    try:
        # 3. Сохраняем ОСНОВНОЙ отчет
        await reports_db.connect()  # На всякий случай

        report_id = await reports_db.save_main_report(
            user=real_name,
            district=district_name,
            road=road_formatted,
            lpu=lpu_name,
            doctor_name=doc_name,
            doctor_spec=doc_spec,
            doctor_number=doc_num,
            term=terms,
            comment=comment
        )

        # 4. Сохраняем ПРЕПАРАТЫ
        selected_ids = data.get("selected_items", [])
        prep_map = data.get("prep_map", {})

        prep_names = []
        for pid in selected_ids:
            name = prep_map.get(pid) or prep_map.get(str(pid)) or f"Unknown ID {pid}"
            prep_names.append(name)

        if prep_names:
            await reports_db.save_preps(report_id, prep_names)

        # ==========================================================
        # 🔄 ЛОГИКА ВОЗВРАТА К СПИСКУ ВРАЧЕЙ
        # ==========================================================

        # А. Показываем всплывашку, что все ок
        await callback.answer(f"✅ Отчет по {doc_name} сохранен!", show_alert=False)

        # Б. Чистим ТОЛЬКО данные текущего визита (препараты, комменты)
        # Локацию (lpu_id, district_id) НЕ трогаем!
        await TempDataManager.set(state, "selected_items", [])
        await TempDataManager.set(state, "comms", "")
        await TempDataManager.set(state, "contract_terms", "")
        await TempDataManager.set(state, "doc_name", "")  # Забываем врача

        # В. Генерируем меню врачей заново
        async for session in db_helper.get_pharmacy_session():
            repo = PharmacyRepository(session)

            if lpu_id:
                # Берем список врачей для ТОГО ЖЕ ЛПУ
                doctors = await repo.get_doctors_by_lpu(lpu_id)

                # Создаем клавиатуру
                keyboard = await get_doctors_inline(
                    doctors=doctors,
                    lpu_id=lpu_id,
                    page=1,
                    state=state
                )

                # Г. Меняем сообщение на список врачей
                await state.set_state(PrescriptionFSM.choose_doctor)
                await callback.message.edit_text(
                    f"🏥 <b>{lpu_name}</b>\n"
                    f"✅ Прошлый отчёт ({doc_name}) принят.\n\n"
                    f"👨‍⚕️ <b>Выберите следующего врача:</b>",
                    reply_markup=keyboard
                )
            else:
                # Если ID ЛПУ вдруг потерялся (крайний случай)
                await callback.message.edit_text("✅ Отчет сохранен. Вернитесь в главное меню.")
                await state.clear()

    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        await callback.answer("Ошибка базы данных при сохранении!", show_alert=True)