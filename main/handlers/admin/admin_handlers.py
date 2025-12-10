from aiogram import Router, F, types
from aiogram.types import BufferedInputFile
from datetime import datetime

# Import your database and the Excel generator we created earlier
from loader import reportsDB
from utils.report.excel_generator import create_excel_report
from keyboard.inline.admin_kb import get_admin_menu

router = Router()

# ============================================================
# 📊 ADMIN: EXPORT EXCEL
# ============================================================
@router.callback_query(F.data == "admin_export_xlsx")
async def admin_export_reports(callback: types.CallbackQuery):
    """Generates and sends the full Excel report to the admin."""

    # 1. Notify admin process started (Edit text to avoid multiple clicks)
    await callback.message.edit_text(
        "⏳ <b>Формирую таблицу...</b>\nПожалуйста, подождите, это может занять несколько секунд.")

    try:
        # 2. Fetch All Data (Doctors + Pharmacies)
        doc_data = await reportsDB.fetch_all_doctor_data()
        apt_data = await reportsDB.fetch_all_apothecary_data()

        if not doc_data and not apt_data:
            await callback.message.edit_text(
                "❌ <b>База данных пуста.</b>\nНет отчетов для экспорта.",
                reply_markup=get_admin_menu()
            )
            return

        # 3. Generate Excel File (in memory)
        excel_file = create_excel_report(doc_data, apt_data)

        # 4. Prepare Filename
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"Full_Report_{date_str}.xlsx"

        # 5. Send the File
        file_to_send = BufferedInputFile(excel_file.read(), filename=filename)

        # Send as a new message (document)
        await callback.message.answer_document(
            document=file_to_send,
            caption=f"📊 <b>Сводный отчет (Excel)</b>\n📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )

        # 6. Restore Admin Menu
        await callback.message.answer("Главное меню администратора:", reply_markup=get_admin_menu())

        # Delete the "Processing..." message
        await callback.message.delete()

    except Exception as e:
        # Log error and notify admin
        print(f"Export Error: {e}")
        await callback.message.answer(f"❌ <b>Ошибка при создании отчета:</b>\n{e}", reply_markup=get_admin_menu())

    await callback.answer()