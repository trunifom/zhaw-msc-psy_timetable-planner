# src/export.py
import pandas as pd
import io

def prepare_timetable_for_export(schedule_data) -> pd.DataFrame:
    """
    Transformiert die internen Datenstrukturen (z.B. aus models.py) 
    in einen flachen pandas DataFrame, der optimal für den Export ist.
    """
    # Hier kommt deine Logik hin, um die Daten zu formatieren
    # df = pd.DataFrame(schedule_data)
    # return df
    pass

def generate_excel_download(df: pd.DataFrame) -> bytes:
    """
    Erzeugt ein Excel-Dokument im Arbeitsspeicher (RAM) für den 
    direkten Download in Streamlit, ohne lokale Dateien zu schreiben.
    """
    output = io.BytesIO()
    # Mit der 'xlsxwriter' engine können wir das Layout formatieren
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Stundenplan')
        
        # Optional: Spaltenbreiten anpassen für bessere Lesbarkeit
        worksheet = writer.sheets['Stundenplan']
        for i, col in enumerate(df.columns):
            column_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.set_column(i, i, column_len)
            
    processed_data = output.getvalue()
    return processed_data