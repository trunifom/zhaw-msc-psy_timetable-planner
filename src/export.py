import pandas as pd
import io
from datetime import datetime, date, time
from typing import Iterable


def _escape_ics_text(value: str) -> str:
    """Escape text according to RFC5545 for ICS payloads."""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )

def prepare_timetable_for_export(schedule_data: Iterable) -> pd.DataFrame:
    """
    Transformiert die internen Datenstrukturen (z.B. aus models.py) 
    in einen flachen pandas DataFrame, der optimal für den Export ist.
    """
    rows = []
    for item in schedule_data:
        if hasattr(item, "to_ui_dict"):
            datum_value = getattr(item, "datum", None)
            rows.append(
                {
                    "Modul-Nr": getattr(item, "modul_nr", None) or "",
                    "Kurs-Nr": getattr(item, "kurs_nr", None) or "",
                    "Modul": item.modulname,
                    "Tag": getattr(item.wochentag, "value", item.wochentag).capitalize(),
                    "Datum": datum_value.strftime("%Y-%m-%d") if datum_value else "",
                    "Von": item.startzeit.strftime("%H:%M"),
                    "Bis": item.endzeit.strftime("%H:%M"),
                    "ECTS": item.ects,
                    "Pruefung": "Ja" if getattr(item, "ist_pruefung", False) else "Nein",
                    "Typ": item.modultyp,
                    "Dozent:in": item.dozierende,
                    "Raum": item.raum,
                }
            )
        elif isinstance(item, dict):
            rows.append(item)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    preferred_order = [
        "Modul-Nr",
        "Kurs-Nr",
        "Modul",
        "Tag",
        "Datum",
        "Von",
        "Bis",
        "ECTS",
        "Pruefung",
        "Typ",
        "Dozent:in",
        "Raum",
    ]
    ordered = [col for col in preferred_order if col in df.columns]
    remaining = [col for col in df.columns if col not in ordered]
    return df[ordered + remaining]

def generate_excel_download(df: pd.DataFrame) -> bytes:
    """
    Erzeugt ein Excel-Dokument im Arbeitsspeicher (RAM) für den 
    direkten Download in Streamlit, ohne lokale Dateien zu schreiben.
    """
    output = io.BytesIO()
    if df is None:
        df = pd.DataFrame()

    # Prefer openpyxl because it is already used by pandas for Excel input.
    try:
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Stundenplan")
            worksheet = writer.sheets["Stundenplan"]
            for idx, col in enumerate(df.columns, start=1):
                max_len = max(df[col].astype(str).map(len).max() if not df.empty else 0, len(str(col))) + 2
                col_letter = chr(64 + idx) if idx <= 26 else None
                if col_letter:
                    worksheet.column_dimensions[col_letter].width = min(max_len, 80)
    except Exception:
        output = io.BytesIO()
        with pd.ExcelWriter(output) as writer:
            df.to_excel(writer, index=False, sheet_name="Stundenplan")

    processed_data = output.getvalue()
    return processed_data


def generate_ics_download(schedule_data: Iterable, calendar_name: str = "ZHAW Planner") -> bytes:
    """Create an ICS calendar payload from selected modules."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ZHAW Planner//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{_escape_ics_text(calendar_name)}",
    ]

    now_utc = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    counter = 0

    for module in schedule_data:
        module_date: date | None = getattr(module, "datum", None)
        start_time: time | None = getattr(module, "startzeit", None)
        end_time: time | None = getattr(module, "endzeit", None)
        if not module_date or not start_time or not end_time:
            continue

        dt_start = datetime.combine(module_date, start_time)
        dt_end = datetime.combine(module_date, end_time)
        summary = getattr(module, "modulname", "Modul")
        location = getattr(module, "raum", "") or ""
        lecturer = getattr(module, "dozierende", "") or ""
        modul_nr = getattr(module, "modul_nr", "") or ""
        kurs_nr = getattr(module, "kurs_nr", "") or ""
        exam_flag = "Ja" if getattr(module, "ist_pruefung", False) else "Nein"
        desc_parts = []
        if lecturer and lecturer != "N/A":
            desc_parts.append(f"Dozent:in: {lecturer}")
        if modul_nr:
            desc_parts.append(f"Modul-Nr: {modul_nr}")
        if kurs_nr:
            desc_parts.append(f"Kurs-Nr: {kurs_nr}")
        desc_parts.append(f"Pruefung: {exam_flag}")
        description = " | ".join(desc_parts)

        counter += 1
        uid = f"{module_date.strftime('%Y%m%d')}-{counter}@zhaw-planner"

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{now_utc}",
                f"DTSTART:{dt_start.strftime('%Y%m%dT%H%M%S')}",
                f"DTEND:{dt_end.strftime('%Y%m%dT%H%M%S')}",
                f"SUMMARY:{_escape_ics_text(summary)}",
                f"LOCATION:{_escape_ics_text(location)}",
                f"DESCRIPTION:{_escape_ics_text(description)}",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines).encode("utf-8")