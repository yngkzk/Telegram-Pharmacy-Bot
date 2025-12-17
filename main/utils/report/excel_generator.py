import pandas as pd
import re
from io import BytesIO
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter


def adjust_column_widths(worksheet, df, wrap_cols: list):
    """
    Helper function to autofit columns while handling wrapped text specific columns.
    """
    for i, col in enumerate(df.columns):
        col_idx = i + 1
        col_letter = get_column_letter(col_idx)

        # 1. HANDLE LONG TEXT COLUMNS (Fixed Width + Wrap)
        if col in wrap_cols:
            worksheet.column_dimensions[col_letter].width = 30  # Slightly narrower since we split cols
            for cell in worksheet[col_letter]:
                cell.alignment = Alignment(wrap_text=True, vertical='top')

        # 2. HANDLE STANDARD COLUMNS (Autofit)
        else:
            max_len = df[col].astype(str).map(len).max()
            header_len = len(str(col))
            adjusted_width = max(max_len, header_len) + 2

            if adjusted_width > 30:
                adjusted_width = 30

            worksheet.column_dimensions[col_letter].width = adjusted_width
            for cell in worksheet[col_letter]:
                cell.alignment = Alignment(vertical='top')


def extract_qty(text, kind='req'):
    """
    Parses string like "Заявка: 10 | Остаток: 5"
    """
    text = str(text)
    # Regex to find numbers
    # Matches "Заявка: (digits)" and "Остаток: (digits)"
    match = re.search(r"Заявка:\s*(\d+)\s*\|\s*Остаток:\s*(\d+)", text)
    if match:
        if kind == 'req':
            return match.group(1)
        elif kind == 'rem':
            return match.group(2)
    return text if kind == 'req' else ""  # Fallback: return whole text in Request col if format doesn't match


def create_excel_report(doc_data: list, apt_data: list) -> BytesIO:
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:

        # =========================================================
        # 1. DOCTORS SHEET
        # =========================================================
        if doc_data:
            df = pd.DataFrame(doc_data)

            static_cols = [
                'id', 'date', 'user', 'district', 'road', 'lpu',
                'doc_name', 'doc_spec', 'doc_num', 'term', 'commentary'
            ]
            agg_rules = {col: 'first' for col in static_cols if col in df.columns}
            df_grouped = df.groupby('id').agg(agg_rules)

            # Combine Preps
            df_grouped['prep'] = df.groupby('id')['prep'].apply(
                lambda x: '\n'.join([str(s) for s in x if s])
            )

            df_grouped = df_grouped.reset_index(drop=True)
            df_grouped.rename(columns={
                'id': 'ID', 'date': 'Дата', 'user': 'Сотрудник',
                'district': 'Район', 'road': 'Маршрут', 'lpu': 'ЛПУ',
                'doc_name': 'Врач', 'doc_spec': 'Спец', 'doc_num': 'Телефон',
                'term': 'Условия', 'commentary': 'Комментарий', 'prep': 'Препараты'
            }, inplace=True)

            sheet_name = 'Врачи'
            df_grouped.to_excel(writer, sheet_name=sheet_name, index=False)

            adjust_column_widths(
                writer.sheets[sheet_name],
                df_grouped,
                wrap_cols=['Препараты', 'Комментарий', 'Условия']
            )

        else:
            pd.DataFrame({'Info': ['Нет данных']}).to_excel(writer, sheet_name='Врачи')

        # =========================================================
        # 2. PHARMACIES SHEET (Split Columns)
        # =========================================================
        if apt_data:
            df = pd.DataFrame(apt_data)

            # We can simply use the columns directly now
            # 'request' and 'remaining' come straight from SQL

            static_cols = ['id', 'date', 'user', 'district', 'road', 'lpu_name', 'commentary']
            agg_rules = {col: 'first' for col in static_cols if col in df.columns}
            df_grouped = df.groupby('id').agg(agg_rules)

            # Aggregate the 3 columns separately
            df_grouped['prep_name'] = df.groupby('id')['prep'].apply(
                lambda x: '\n'.join([str(s) for s in x if s])
            )
            df_grouped['req_qty'] = df.groupby('id')['request'].apply(
                lambda x: '\n'.join([str(s) if s and str(s).lower() != 'none' else "0" for s in x])
            )
            df_grouped['rem_qty'] = df.groupby('id')['remaining'].apply(
                lambda x: '\n'.join([str(s) if s and str(s).lower() != 'none' else "0" for s in x])
            )

            df_grouped = df_grouped.reset_index(drop=True)

            df_grouped.rename(columns={
                'id': 'ID', 'date': 'Дата', 'user': 'Сотрудник',
                'district': 'Район', 'road': 'Маршрут', 'lpu_name': 'Аптека',
                'commentary': 'Комментарий',
                'prep_name': 'Препарат',
                'req_qty': 'Заявка',
                'rem_qty': 'Остаток'
            }, inplace=True)

            # 5. WRITE
            sheet_name = 'Аптеки'
            df_grouped.to_excel(writer, sheet_name=sheet_name, index=False)

            # 6. STYLE
            adjust_column_widths(
                writer.sheets[sheet_name],
                df_grouped,
                wrap_cols=['Препарат', 'Заявка', 'Остаток', 'Комментарий']
            )

        else:
            pd.DataFrame({'Info': ['Нет данных']}).to_excel(writer, sheet_name='Аптеки')

    output.seek(0)
    return output