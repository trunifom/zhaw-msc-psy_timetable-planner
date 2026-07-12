import pandas as pd
from typing import List
from models import ZHAWModule
from datetime import datetime

def parse_time(time_str: str):
    """Konvertiert einen String (z.B. '09:50') in ein datetime.time Objekt."""
    return datetime.strptime(time_str.strip(), "%H:%M").time()

def load_schedule_from_dataframe(df: pd.DataFrame) -> List[ZHAWModule]:
    """Validiert die hochgeladenen Daten und wandelt sie in Pydantic-Modelle um."""
    modules = []
    
    # Bereinigung: NAs entfernen oder auffüllen
    df = df.dropna(subset=['Modulname', 'Wochentag', 'Startzeit', 'Endzeit'])
    
    for _, row in df.iterrows():
        try:
            mod = ZHAWModule(
                modulname=str(row['Modulname']),
                modultyp=str(row['Modultyp']),
                ects=int(row['ECTS']),
                wochentag=str(row['Wochentag']),
                startzeit=parse_time(str(row['Startzeit'])),
                endzeit=parse_time(str(row['Endzeit'])),
                dozierende=str(row['Dozierende']) if 'Dozierende' in df.columns else None
            )
            modules.append(mod)
        except Exception as e:
            # In Produktion: Logs schreiben. Hier werfen wir den Fehler für das UI weiter.
            raise ValueError(f"Fehler beim Parsen von Modul {row.get('Modulname')}: {e}")
            
    return modules