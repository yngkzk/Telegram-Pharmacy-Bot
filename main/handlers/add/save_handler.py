from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

# 🔥 ТОЛЬКО НОВЫЕ ИМПОРТЫ РЕПОЗИТОРИЕВ
from infrastructure.database.repo.user_repo import UserRepository
from infrastructure.database.repo.pharmacy_repo import PharmacyRepository
from infrastructure.database.repo.report_repo import ReportRepository

from states.add.prescription_state import PrescriptionFSM
from keyboard.inline.inline_buttons import get_doctors_inline
from utils.logger.logger_config import logger

router = Router()


@router.callback_query(F.data == "confirm_yes", PrescriptionFSM.confirmation)
async def final_save_report(
        callback: types.CallbackQuery,
        state: FSMContext,
        reports_db: ReportRepository,
        user_repo: UserRepository,
        pharmacy_repo: PharmacyRepository
):
    """
    Финальное сохранение отчета (Работает и для Врачей, и для Аптек).
    """
    user_id = callback.from_user.id
    real_name = callback.from_user.full_name or f"User_{user_id}"

    # 1. Получаем Имя через DI (без async for)
    user_db = await user_repo.get_user(user_id)
    if user_db and user_db.user_name:
        real_name = user_db.user_name

    # 2. Получаем данные из нативного FSM
    data = await state.get_data()
    prefix = data.get("prefix")

    district_name = data.get("district_name")
    road_num = data.get("road_num")
    apt_name = data.get("apt_name")
    lpu_name = data.get("lpu_name")
    lpu_id = data.get("lpu_id")
    comment = data.get("comms", "")

    if not district_name or not road_num:
        await callback.answer("Ошибка: Данные локации потеряны. Начните заново.", show_alert=True)
        await state.clear()
        return

    try:
        # ==========================================
        # 👨‍⚕️ ВЕТКА СОХРАНЕНИЯ ВРАЧА (doc)
        # ==========================================
        if prefix == "doc":
            doc_name = data.get("doc_name", "Неизвестный врач")
            doc_spec = data.get("doc_spec")

            if not doc_spec or str(doc_spec).strip().lower() in ["нет", "none", "", "-"]:
                doc_spec = "Не указана"

            doc_num = data.get("doc_num")
            terms = data.get("contract_terms") or "Нет условий"

            # Сохраняем ОСНОВНОЙ отчет (возвращает объект модели)
            report = await reports_db.save_main_report(
                user=real_name,
                district=district_name,
                road=road_num,  # Передаем int, как прописано в модели
                lpu=lpu_name,
                doctor_name=doc_name,
                doctor_spec=doc_spec,
                doctor_number=str(doc_num) if doc_num else None,
                term=terms,
                comment=comment
            )

            # Сохраняем ПРЕПАРАТЫ
            selected_ids = data.get("selected_items", [])
            prep_map = data.get("prep_map", {})
            prep_names = []

            for pid in selected_ids:
                name = prep_map.get(str(pid)) or prep_map.get(int(pid)) or f"Unknown ID {pid}"
                prep_names.append(name)

            if prep_names:
                await reports_db.save_preps(report.id, prep_names)

            await callback.answer("✅ Отчет по врачу сохранен!", show_alert=False)

            # Очищаем только данные о враче, чтобы выбрать следующего
            await state.update_data(
                selected_items=[],
                comms="",
                contract_terms="",
                doc_name=""
            )

            if lpu_id:
                doctors = await pharmacy_repo.get_doctors_by_lpu(lpu_id)
                keyboard = await get_doctors_inline(doctors, lpu_id=lpu_id, page=1, state=state)

                await state.set_state(PrescriptionFSM.choose_doctor)
                await callback.message.edit_text(
                    f"🏥 <b>{lpu_name}</b>\n"
                    f"✅ Прошлый отчёт ({doc_name}) принят.\n\n"
                    f"👨‍⚕️ <b>Выберите следующего врача:</b>",
                    reply_markup=keyboard
                )
            else:
                await callback.message.edit_text("✅ Отчет сохранен. Вернитесь в главное меню.")
                await state.clear()


        # ==========================================
        # 🏪 ВЕТКА СОХРАНЕНИЯ АПТЕКИ (apt)
        # ==========================================
        elif prefix == "apt":
            final_quantities = data.get("final_quantities", {})
            prep_map = data.get("prep_map", {})

            # Сохраняем отчет (возвращает объект модели)
            report = await reports_db.save_apothecary_report(
                user=real_name,
                district=district_name,
                road=road_num,  # Передаем int
                lpu=apt_name,
                comment=comment
            )

            # Формируем список кортежей (name, req, rem) для нового метода
            items_to_save = []
            for p_id_str, vals in final_quantities.items():
                name = prep_map.get(str(p_id_str)) or prep_map.get(int(p_id_str)) or f"ID {p_id_str}"
                items_to_save.append((name, vals['req'], vals['rem']))

            if items_to_save:
                await reports_db.save_apothecary_preps(report.id, items_to_save)

            await callback.answer("✅ Отчет по аптеке сохранен!", show_alert=False)
            await callback.message.edit_text(
                f"✅ Отчет по аптеке <b>{apt_name}</b> успешно сохранен!\n\n"
                f"Нажмите /start или выберите действие в меню."
            )
            await state.clear()

        else:
            await callback.answer("❌ Ошибка: Неизвестный тип отчета.", show_alert=True)

    except Exception as e:
        logger.error(f"❌ Ошибка сохранения отчета: {e}", exc_info=True)
        await callback.answer("Ошибка базы данных при сохранении!", show_alert=True)