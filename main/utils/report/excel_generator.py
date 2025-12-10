import pandas as pd
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
            worksheet.column_dimensions[col_letter].width = 50
            for cell in worksheet[col_letter]:
                cell.alignment = Alignment(wrap_text=True, vertical='top')

        # 2. HANDLE STANDARD COLUMNS (Autofit)
        else:
            # Calculate max length of data or header
            max_len = df[col].astype(str).map(len).max()
            header_len = len(str(col))

            # Add a little padding (+2)
            adjusted_width = max(max_len, header_len) + 2

            # Set a safety cap (e.g., max 30 chars for standard columns)
            if adjusted_width > 30:
                adjusted_width = 30

            worksheet.column_dimensions[col_letter].width = adjusted_width

            # Align standard cells to top-left for consistency
            for cell in worksheet[col_letter]:
                cell.alignment = Alignment(vertical='top')


def create_excel_report(doc_data: list, apt_data: list) -> BytesIO:
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:

        # =========================================================
        # 1. DOCTORS SHEET
        # =========================================================
        if doc_data:
            df = pd.DataFrame(doc_data)

            # Grouping Logic
            static_cols = [
                'id', 'date', 'user', 'district', 'road', 'lpu',
                'doc_name', 'doc_spec', 'doc_num', 'term', 'commentary'
            ]
            agg_rules = {col: 'first' for col in static_cols if col in df.columns}
            df_grouped = df.groupby('id').agg(agg_rules)

            # Join Preps
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

            # Write
            sheet_name = 'Врачи'
            df_grouped.to_excel(writer, sheet_name=sheet_name, index=False)

            # Apply Formatting
            adjust_column_widths(
                writer.sheets[sheet_name],
                df_grouped,
                wrap_cols=['Препараты', 'Комментарий', 'Условия']
            )

        else:
            pd.DataFrame({'Info': ['Нет данных']}).to_excel(writer, sheet_name='Врачи')

        # =========================================================
        # 2. PHARMACIES SHEET
        # =========================================================
        if apt_data:
            df = pd.DataFrame(apt_data)

            # Format Logic
            df['full_prep_info'] = df.apply(
                lambda row: f"{row['prep']} — {row['remaining']}" if row.get('prep') else "",
                axis=1
            )

            static_cols = ['id', 'date', 'user', 'district', 'road', 'lpu_name', 'commentary']
            agg_rules = {col: 'first' for col in static_cols if col in df.columns}
            df_grouped = df.groupby('id').agg(agg_rules)

            df_grouped['preps_combined'] = df.groupby('id')['full_prep_info'].apply(
                lambda x: '\n'.join([str(s) for s in x if s])
            )

            df_grouped = df_grouped.reset_index(drop=True)
            df_grouped.rename(columns={
                'id': 'ID', 'date': 'Дата', 'user': 'Сотрудник',
                'district': 'Район', 'road': 'Маршрут', 'lpu_name': 'Аптека',
                'commentary': 'Комментарий', 'preps_combined': 'Препараты (Заявка/Остаток)'
            }, inplace=True)

            # Write
            sheet_name = 'Аптеки'
            df_grouped.to_excel(writer, sheet_name=sheet_name, index=False)

            # Apply Formatting
            adjust_column_widths(
                writer.sheets[sheet_name],
                df_grouped,
                wrap_cols=['Препараты (Заявка/Остаток)', 'Комментарий']
            )

        else:
            pd.DataFrame({'Info': ['Нет данных']}).to_excel(writer, sheet_name='Аптеки')

    output.seek(0)
    return output