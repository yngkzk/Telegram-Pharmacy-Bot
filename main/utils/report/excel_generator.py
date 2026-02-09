import io
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter


def create_excel_report(doc_data: list, apt_data: list) -> io.BytesIO:
    """
    Генерирует Excel файл с двумя листами: Врачи и Аптеки.
    """
    wb = Workbook()

    # ==========================================
    # 📄 ЛИСТ 1: ОТЧЕТЫ ПО ВРАЧАМ
    # ==========================================
    ws1 = wb.active
    ws1.title = "Врачи"

    # Заголовки
    headers1 = [
        "ID", "Дата", "Сотрудник",
        "Район", "Маршрут", "ЛПУ",
        "Врач", "Специальность", "Телефон",
        "Условия", "Препараты", "Комментарий"
    ]
    ws1.append(headers1)

    # Данные
    if doc_data:
        for row in doc_data:
            # Превращаем объект строки БД в список значений
            # Порядок должен совпадать с заголовками!
            ws1.append([
                row['id'],
                row['created_at'],
                row['user_name'],
                row['district'],
                row['road'],
                row['lpu'],
                row['doctor_name'],
                row['doctor_spec'],
                row['doctor_number'],
                row['term'],
                row['preps'],  # Список препаратов
                row['commentary']
            ])

    # ==========================================
    # 📄 ЛИСТ 2: ОТЧЕТЫ ПО АПТЕКАМ
    # ==========================================
    ws2 = wb.create_sheet(title="Аптеки")

    headers2 = [
        "ID", "Дата", "Сотрудник",
        "Район", "Маршрут", "Точка (Аптека)",
        "Препарат", "Заявка (шт)", "Остаток (шт)",
        "Комментарий"
    ]
    ws2.append(headers2)

    if apt_data:
        for row in apt_data:
            ws2.append([
                row['id'],
                row['created_at'],
                row['user_name'],
                row['district'],
                row['road'],
                row['lpu'],  # Название аптеки
                row['prep_name'],  # Имя препарата из связанной таблицы
                row['req_qty'],  # Число (float/int)
                row['rem_qty'],  # Число (float/int)
                row['commentary']
            ])

    # ==========================================
    # 🎨 ОФОРМЛЕНИЕ (АВТО-ШИРИНА)
    # ==========================================
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")

    for ws in wb.worksheets:
        # Красим заголовки
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")

        # Авто-подбор ширины столбцов (FIXED ERROR)
        for col in ws.columns:
            max_length = 0
            column_letter = get_column_letter(col[0].column)

            for cell in col:
                try:
                    # 🔥 ГЛАВНОЕ ИСПРАВЛЕНИЕ:
                    # Мы принудительно делаем str(cell.value),
                    # чтобы len() не падал на числах (float/int)
                    if cell.value:
                        cell_len = len(str(cell.value))
                        if cell_len > max_length:
                            max_length = cell_len
                except:
                    pass

            # Немного запаса ширины
            adjusted_width = (max_length + 2)
            # Ограничиваем, чтобы колонка не стала гигантской (макс 50 символов)
            if adjusted_width > 50:
                adjusted_width = 50

            ws.column_dimensions[column_letter].width = adjusted_width

    # ==========================================
    # 💾 СОХРАНЕНИЕ В ПАМЯТЬ
    # ==========================================
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return output