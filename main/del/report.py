# from aiogram import Router, F, types
# from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
# from aiogram.fsm.context import FSMContext
#
# # Импортируем типы баз данных
# from db.database import BotDB
# from db.reports import ReportRepository
#
# from storage.temp_data import TempDataManager
# from keyboard.inline.menu_kb import get_main_menu_inline
# from keyboard.inline.inline_select import get_prep_inline
#
# from utils.logger.logger_config import logger
# from states.add.prescription_state import PrescriptionFSM
#
# router = Router()
#
#
# # ============================================================
# # 📥 ПОЛУЧЕНИЕ ДАННЫХ ИЗ STATE (Helper)
# # ============================================================
# async def _get_report_data(state: FSMContext, pharmacy_db: BotDB):
#     data = await TempDataManager.get_all(state)
#     prefix = data.get("prefix")
#
#     if not prefix:
#         if data.get("final_quantities"):
#             prefix = "apt"
#         elif data.get("doc_name"):
#             prefix = "doc"
#         else:
#             prefix = "unknown"
#
#     # Загружаем карту препаратов из pharmacy_db (там лежат лекарства)
#     raw_rows = await pharmacy_db.get_prep_list()
#     prep_items = [(row["id"], row["prep"]) for row in raw_rows]
#     prep_map = {str(item_id): name for item_id, name in prep_items}
#     for item_id, name in prep_items:
#         prep_map[item_id] = name
#
#     selected_ids = data.get("selected_items", [])
#     selected_names_list = []
#
#     for i in selected_ids:
#         name = prep_map.get(i) or prep_map.get(str(i)) or f"ID {i}"
#         selected_names_list.append(name)
#
#     return data, prefix, prep_map, selected_names_list
#
#
# # ============================================================
# # 📄 ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР (SHOW CARD)
# # ============================================================
# @router.callback_query(F.data == "show_card", PrescriptionFSM.confirmation)
# async def show_card(callback: CallbackQuery, state: FSMContext, pharmacy_db: BotDB):
#     data, prefix, prep_map, selected_names_list = await _get_report_data(state, pharmacy_db)
#
#     quantities = data.get("final_quantities", {})
#     selected_text = "Список пуст"
#
#     if prefix == "apt" and quantities:
#         lines = []
#         for med_id, val in quantities.items():
#             name = prep_map.get(med_id) or prep_map.get(str(med_id)) or f"ID {med_id}"
#             if isinstance(val, dict):
#                 req = val.get('req', 0)
#                 rem = val.get('rem', 0)
#                 lines.append(f"▫️ {name} — <b>Заявка: {req} / Остаток: {rem}</b>")
#             else:
#                 lines.append(f"▫️ {name} — <b>{val}</b>")
#         selected_text = "\n".join(lines)
#
#     elif prefix == "doc" and selected_names_list:
#         lines = [f"▫️ {name}" for name in selected_names_list]
#         selected_text = "\n".join(lines)
#
#     lpu_name = data.get('lpu_name', 'Не указано')
#     text = f"📋 <b>ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР</b>\n➖➖➖➖➖➖➖➖➖➖\n"
#
#     if prefix == "doc":
#         doc_name = data.get('doc_name', 'Не указан')
#         doc_spec = data.get('doc_spec') or 'Нет'
#         text += (
#             f"📍 <b>ЛПУ:</b> {lpu_name}\n"
#             f"👨‍⚕️ <b>Врач:</b> {doc_name}\n"
#             f"🩺 <b>Спец:</b> {doc_spec}\n"
#         )
#         if data.get('term'):
#             text += f"📝 <b>Условия:</b> {data.get('term')}\n"
#
#     elif prefix == "apt":
#         text += f"🏥 <b>Аптека:</b> {lpu_name}\n"
#
#     comms = data.get('comms') or "Без комментария"
#     text += (
#         f"➖➖➖➖➖➖➖➖➖➖\n"
#         f"💊 <b>Препараты:</b>\n{selected_text}\n\n"
#         f"💬 <b>Комментарий:</b> {comms}"
#     )
#
#     kb = InlineKeyboardMarkup(inline_keyboard=[
#         [
#             InlineKeyboardButton(text="✅ Сохранить", callback_data="confirm_yes"),
#             InlineKeyboardButton(text="✏️ Изменить", callback_data="back_to_meds")
#         ]
#     ])
#
#     try:
#         await callback.message.edit_text(text, reply_markup=kb)
#     except Exception:
#         await callback.message.answer(text, reply_markup=kb)
#     await callback.answer()
#
#
# @router.callback_query(F.data == "back_to_meds")
# async def back_to_med_selection(callback: CallbackQuery, state: FSMContext, pharmacy_db: BotDB):
#     data, prefix, _, _ = await _get_report_data(state, pharmacy_db)
#     keyboard = await get_prep_inline(pharmacy_db, state, prefix=prefix)
#     await state.set_state(PrescriptionFSM.choose_meds)
#     await callback.message.answer("💊 <b>Выберите препараты:</b>", reply_markup=keyboard)
#     try:
#         await callback.message.delete()
#     except:
#         pass
#
#
# # ============================================================
# # 💾 СОХРАНЕНИЕ В БД (UPLOAD REPORT)
# # ============================================================
# @router.callback_query(F.data.in_(["confirm_yes", "mp_up"]), PrescriptionFSM.confirmation)
# async def upload_report(
#         callback: CallbackQuery,
#         state: FSMContext,
#         pharmacy_db: BotDB,  # Для лекарств
#         reports_db: ReportRepository,  # Для сохранения отчетов
#         accountant_db: BotDB  # 🔥 ДОБАВИЛИ: Для получения имени пользователя
# ):
#     # 1. Получаем имя пользователя из accountant_db (по ID телеграма)
#     real_name = await accountant_db.get_active_username(callback.from_user.id)
#
#     # Если вдруг не нашли, берем из телеграма
#     user_name = real_name if real_name else callback.from_user.full_name
#
#     # 2. Собираем остальные данные
#     data, prefix, prep_map, selected_names_list = await _get_report_data(state, pharmacy_db)
#
#     district_id = data.get("district")
#     road_num = data.get("road")
#
#     try:
#         district_name = str(district_id)
#         road_name = f"Маршрут {road_num}"
#     except Exception:
#         district_name = "Unknown"
#         road_name = "Unknown"
#
#     logger.info(f"Saving report... User: {user_name}, Prefix: {prefix}")
#
#     try:
#         if prefix == "apt":
#             lpu_name = data.get("lpu_name")
#
#             # Сохраняем (user_name теперь правильный)
#             report_id = await reports_db.save_apothecary_report(
#                 user=user_name,
#                 district=district_name,
#                 road=road_name,
#                 lpu=lpu_name,
#                 comment=data.get("comms", "-")
#             )
#
#             quantities = data.get("final_quantities", {})
#             items_to_save = []
#             for med_id, val in quantities.items():
#                 med_name = prep_map.get(med_id) or prep_map.get(str(med_id)) or f"ID {med_id}"
#                 if isinstance(val, dict):
#                     req = val.get('req', 0)
#                     rem = val.get('rem', 0)
#                 else:
#                     req = 0
#                     rem = val
#                 items_to_save.append((med_name, req, rem))
#
#             await reports_db.save_apothecary_preps(report_id, items_to_save)
#             success_text = f"✅ <b>Отчёт по аптеке «{lpu_name}» сохранён!</b>"
#
#         elif prefix == "doc":
#             # Сохраняем (user_name теперь правильный)
#             report_id = await reports_db.save_main_report(
#                 user=user_name,
#                 district=district_name,
#                 road=road_name,
#                 lpu=data.get("lpu_name"),
#                 doctor_name=data.get("doc_name"),
#                 doctor_spec=data.get("doc_spec"),
#                 doctor_number=data.get("doc_num", "Unknown"),
#                 term=data.get("term"),
#                 comment=data.get("comms", "-")
#             )
#
#             await reports_db.save_preps(report_id, selected_names_list)
#             success_text = "✅ <b>Отчёт по врачу сохранён!</b>"
#
#         else:
#             await callback.message.answer("⚠️ Ошибка: Не удалось определить тип отчета.")
#             return
#
#         await callback.message.edit_text(success_text)
#
#         # Возвращаем меню
#         kb = await get_main_menu_inline(callback.from_user.id, reports_db)
#         await callback.message.answer("Что делаем дальше?", reply_markup=kb)
#
#         await state.clear()
#
#     except Exception as e:
#         logger.critical(f"Error saving report: {e}")
#         await callback.message.answer(f"❌ Ошибка при сохранении: {e}")
#         await callback.answer()