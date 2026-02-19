from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

# Импорты БД
from infrastructure.database.db_helper import db_helper
from infrastructure.database.repo.user_repo import UserRepository
from infrastructure.database.repo.pharmacy_repo import PharmacyRepository
from db.reports import ReportRepository

from storage.temp_data import TempDataManager
from states.add.prescription_state import PrescriptionFSM
from keyboard.inline.inline_buttons import get_doctors_inline

router = Router()


@router.callback_query(F.data == "confirm_yes", PrescriptionFSM.confirmation)
async def final_save_report(
        callback: types.CallbackQuery,
        state: FSMContext,
        reports_db: ReportRepository
):
    """
    Финальное сохранение отчета (Работает и для Врачей, и для Аптек).
    """
    # ==========================================
    # 1. БЕЗОПАСНОЕ ПОЛУЧЕНИЕ ИМЕНИ СОТРУДНИКА
    # ==========================================
    user_id = callback.from_user.id
    real_name = callback.from_user.full_name or f"User_{user_id}"

    async for u_session in db_helper.get_user_session():
        u_repo = UserRepository(u_session)
        user_db = await u_repo.get_user(user_id)

        if user_db:
            db_name = getattr(user_db, 'user_name', None) or \
                      getattr(user_db, 'name', None) or \
                      getattr(user_db, 'username', None)
            if db_name:
                real_name = db_name

    # ==========================================
    # 2. ПОЛУЧЕНИЕ ДАННЫХ ИЗ ПАМЯТИ
    # ==========================================
    data = await TempDataManager.get_all(state)
    prefix = data.get("prefix")  # 'doc' или 'apt'

    district_name = data.get("district_name")
    road_num = data.get("road_num")
    apt_name = data.get("apt_name")
    lpu_name = data.get("lpu_name")
    lpu_id = data.get("lpu_id")
    comment = data.get("comms", "")

    # Проверка на целостность данных локации
    if not district_name or not road_num:
        await callback.answer("Ошибка: Данные локации потеряны. Начните заново.", show_alert=True)
        await state.clear()
        return

    road_formatted = f"Маршрут {road_num}" if road_num else "Не указан"

    try:
        await reports_db.connect()

        # ==========================================
        # 👨‍⚕️ ВЕТКА СОХРАНЕНИЯ ВРАЧА (doc)
        # ==========================================
        if prefix == "doc":
            doc_name = data.get("doc_name", "Неизвестный врач")

            # 🔥 Жестко убираем "Нет" из специальности
            doc_spec = data.get("doc_spec")
            if not doc_spec or str(doc_spec).strip().lower() in ["нет", "none", "", "-"]:
                doc_spec = "Не указана"

            doc_num = data.get("doc_num")
            terms = data.get("contract_terms") or "Нет условий"

            # Сохраняем ОСНОВНОЙ отчет
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

            # Сохраняем ПРЕПАРАТЫ
            selected_ids = data.get("selected_items", [])
            prep_map = data.get("prep_map", {})
            prep_names = []

            for pid in selected_ids:
                name = prep_map.get(str(pid)) or prep_map.get(int(pid)) or f"Unknown ID {pid}"
                prep_names.append(name)

            if prep_names:
                await reports_db.save_preps(report_id, prep_names)

            await callback.answer(f"✅ Отчет по врачу сохранен!", show_alert=False)

            # 🔄 ВОЗВРАТ К СПИСКУ ВРАЧЕЙ ЭТОЙ БОЛЬНИЦЫ
            await TempDataManager.set(state, "selected_items", [])
            await TempDataManager.set(state, "comms", "")
            await TempDataManager.set(state, "contract_terms", "")
            await TempDataManager.set(state, "doc_name", "")

            async for session in db_helper.get_pharmacy_session():
                repo = PharmacyRepository(session)
                if lpu_id:
                    doctors = await repo.get_doctors_by_lpu(lpu_id)
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

            # ⚠️ ВНИМАНИЕ: Здесь вызываются методы для аптеки.
            # Убедись, что в файле db/reports.py у тебя есть метод save_apothecary_report
            # Если он называется иначе (например, save_apt_report), поменяй название ниже!

            report_id = await reports_db.save_apothecary_report(
                user=real_name,
                district=district_name,
                road=road_formatted,
                apothecary=apt_name,
                comment=comment
            )

            # Сохраняем препараты аптеки (заявка/остаток)
            if final_quantities:
                # Если у тебя есть специальный метод для препаратов аптеки, вызови его.
                # Я передаю словарь final_quantities (там лежат {'req': X, 'rem': Y})
                await reports_db.save_apothecary_preps(report_id, final_quantities, prep_map)

            await callback.answer(f"✅ Отчет по аптеке сохранен!", show_alert=False)
            await callback.message.edit_text(
                f"✅ Отчет по аптеке <b>{lpu_name}</b> успешно сохранен!\n\n"
                f"Нажмите /start или выберите действие в меню."
            )
            await state.clear()


        # Если prefix сломался
        else:
            await callback.answer("❌ Ошибка: Неизвестный тип отчета (prefix потерян).", show_alert=True)
            return

    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        await callback.answer(f"Ошибка базы данных при сохранении! ({e})", show_alert=True)