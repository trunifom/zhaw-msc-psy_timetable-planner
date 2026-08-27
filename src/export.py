"""
ZHAW MSc Psychology - Timetable Planner (Export Layer)
Description: Turns a list of validated `ZHAWModule` objects (models.py)
into downloadable files - an Excel/XLSX schedule and an RFC5545 calendar
(.ics) that Outlook/Google/Apple Calendar and any other standard calendar
app can import.

Everything here works purely in-memory (`io.BytesIO`) and returns raw
`bytes` - nothing is ever written to disk, matching the app's "no data
persistence" privacy stance (see README.md "Datenschutz").

ICS design notes (see `generate_ics_download`'s docstring for the full
rationale): every module produces exactly one calendar event, in local
Europe/Zurich time converted to UTC (no external timezone dependency),
folded to RFC5545's 75-octet line length, with exams visually marked and
given extra reminders, and category tags that let supporting calendar
apps auto-color events by course.
"""

import pandas as pd
import io
import re
import logging
from datetime import datetime, date, time, timedelta, timezone
from typing import Iterable, Any

# Same self-contained per-module logging pattern as data_loader.py/app.py -
# see app.py's "0. LOGGING" section for why (Streamlit never surfaces this
# in the UI; it only ever reaches the terminal running `streamlit run`).
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(_handler)


def _escape_ics_text(value: str) -> str:
    """Escape text according to RFC5545 for ICS payloads."""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold_ics_line(line: str) -> str:
    """
    Fold a content line to a maximum of 75 octets per RFC5545 (section 3.1),
    with continuation lines prefixed by a single space. Strict calendar
    clients (e.g. Outlook) can silently truncate or reject long unfolded
    lines, which is why SUMMARY/DESCRIPTION lines need this once real
    module details are appended.
    """
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line

    segments = []
    start = 0
    limit = 75
    while start < len(encoded):
        end = min(start + limit, len(encoded))
        # Never split in the middle of a multi-byte UTF-8 sequence.
        while end < len(encoded) and (encoded[end] & 0xC0) == 0x80:
            end -= 1
        segments.append((" " if start else "") + encoded[start:end].decode("utf-8"))
        start = end
        limit = 74  # continuation lines: 1 leading space + 74 content octets = 75 total
    return "\r\n".join(segments)


def _last_sunday(year: int, month: int) -> date:
    """Return the date of the last Sunday in the given month/year."""
    next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    last_day = next_month - timedelta(days=1)
    return last_day - timedelta(days=(last_day.weekday() - 6) % 7)


def _is_zurich_dst(local_dt: datetime) -> bool:
    """EU DST rule: clocks go forward last Sunday of March 02:00, back last Sunday of October 03:00."""
    dst_start = datetime.combine(_last_sunday(local_dt.year, 3), time(2, 0))
    dst_end = datetime.combine(_last_sunday(local_dt.year, 10), time(3, 0))
    return dst_start <= local_dt < dst_end


def _zurich_to_utc(local_dt: datetime) -> datetime:
    """
    Convert a naive Europe/Zurich wall-clock datetime to UTC.
    Implemented without zoneinfo/pytz so it works without an IANA tzdata
    package being installed (notably on plain Windows Python installs).
    """
    offset = timedelta(hours=2) if _is_zurich_dst(local_dt) else timedelta(hours=1)
    return local_dt - offset


def _clean_field(value: Any) -> str | None:
    """Return a trimmed string, or None if the value is empty/a placeholder."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() == "N/A":
        return None
    return text


def _format_number(value: Any) -> str | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return f"{number:g}"


def _uid_base(module: Any) -> str:
    """Build a stable, mostly-ASCII UID fragment (course code preferred over a raw counter)."""
    raw = (
        _clean_field(getattr(module, "kurs_nr", None))
        or _clean_field(getattr(module, "modul_nr", None))
        or getattr(module, "modulname", "modul")
    )
    slug = re.sub(r"[^A-Za-z0-9]+", "-", str(raw)).strip("-").lower()
    return slug or "modul"


_EXAM_SUFFIX_RE = re.compile(r"\s*/\s*PR(?:UE|U|Ü)FUNG\s*$", re.IGNORECASE)


def _event_summary(module: Any, has_date: bool) -> str:
    """
    Keep the title short for narrow calendar-grid views. Only genuine
    exceptions (exam, missing date) get a visual marker - regular sessions
    stay undecorated so the exceptions actually stand out.
    """
    name = _clean_field(getattr(module, "modulname", None)) or "Modul"
    is_exam = bool(getattr(module, "ist_pruefung", False))
    if is_exam:
        # Source names often already end in "/ Pruefung" (ZHAW export
        # convention); drop it here since the marker below says the same.
        name = _EXAM_SUFFIX_RE.sub("", name) or name
    if is_exam and not has_date:
        return f"⚠️ Pruefung (Datum unbekannt): {name}"
    if is_exam:
        return f"⚠️ Pruefung: {name}"
    if not has_date:
        return f"❓ Kein Datum: {name}"
    return name


def _event_description(module: Any, has_date: bool) -> str:
    """
    Build a multi-line description, most actionable/relevant info first.
    Details already visible elsewhere in the calendar UI (start/end time
    for a properly dated event) are left out to avoid clutter.
    """
    lines: list[str] = []

    if not has_date:
        wochentag = getattr(module, "wochentag", None)
        wochentag_label = str(getattr(wochentag, "value", wochentag) or "").capitalize()
        start_time = getattr(module, "startzeit", None)
        end_time = getattr(module, "endzeit", None)
        lines.append(
            "Hinweis: Fuer dieses Modul liegt in der Excelliste kein Datum vor. "
            "Bitte Wochentag/Zeit unten manuell mit Eventoweb/myZHAW abgleichen."
        )
        if wochentag_label and start_time and end_time:
            lines.append(f"Laut Excelliste: {wochentag_label}, {start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')}")
        lines.append("")

    dozierende = _clean_field(getattr(module, "dozierende", None))
    modul_nr = _clean_field(getattr(module, "modul_nr", None))
    kurs_nr = _clean_field(getattr(module, "kurs_nr", None))
    modultyp = _clean_field(getattr(module, "modultyp", None))
    ects = getattr(module, "ects", None)
    attendance = _format_number(getattr(module, "anwesenheitspflicht_prozent", None))
    ist_pruefung = getattr(module, "ist_pruefung", False)

    if dozierende:
        lines.append(f"Dozent:in: {dozierende}")

    if modul_nr and kurs_nr and modul_nr != kurs_nr:
        lines.append(f"Modul/Kurs: {modul_nr} / {kurs_nr}")
    elif kurs_nr:
        lines.append(f"Kurs-Nr: {kurs_nr}")
    elif modul_nr:
        lines.append(f"Modul-Nr: {modul_nr}")

    if modultyp:
        lines.append(f"Modulart: {modultyp}")
    if ects is not None:
        lines.append(f"ECTS: {ects}")
    if attendance is not None:
        lines.append(f"Anwesenheitspflicht: {attendance}%")
    if ist_pruefung:
        lines.append("Pruefung: Ja")
    if getattr(module, "ist_zusatzmodul", False):
        # See docs/planung/KONZEPT-passerelle-zusatzmodule.md section 4.5 -
        # a Passerelle student's supplementary-module sessions look
        # identical to their main-list sessions once exported into a
        # calendar app, so this line is the only place that distinction
        # survives outside the app itself.
        lines.append("Zusatzmodul (Passerelle)")

    return "\n".join(lines)

def prepare_timetable_for_export(schedule_data: Iterable) -> pd.DataFrame:
    """
    Transformiert die internen Datenstrukturen (z.B. aus models.py)
    in einen flachen pandas DataFrame, der optimal für den Export ist.

    Feeds `generate_excel_download` below - this is the Excel/XLSX export
    path only (the ICS/calendar path further down builds its own text
    directly from the ZHAWModule objects, it doesn't go through this
    DataFrame). Accepts either real `ZHAWModule` objects (detected via
    `hasattr(item, "to_ui_dict")`, duck-typed rather than isinstance-checked
    so any object with that method works) or plain dicts, so callers that
    already have a dict-shaped row don't need to wrap it in a ZHAWModule
    just to export it.
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
                    # See docs/planung/KONZEPT-passerelle-zusatzmodule.md
                    # section 4.5 - hardcoded German like every other column
                    # here, since this file has no i18n dependency at all
                    # (unlike app.py's in-UI tables via t()/c()).
                    "Quelle": "Zusatzmodul" if getattr(item, "ist_zusatzmodul", False) else "Hauptliste",
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
        "Quelle",
    ]
    ordered = [col for col in preferred_order if col in df.columns]
    remaining = [col for col in df.columns if col not in ordered]
    return df[ordered + remaining]

def generate_excel_download(df: pd.DataFrame) -> bytes:
    """
    Erzeugt ein Excel-Dokument im Arbeitsspeicher (RAM) für den
    direkten Download in Streamlit, ohne lokale Dateien zu schreiben.

    Column widths are auto-sized to fit their longest value/header (capped
    at 80 characters so one very long cell can't blow up the whole sheet).
    Only the first 26 columns (A-Z) get width tuning via `chr(64 + idx)` -
    a real export never has that many columns, so this simple single-letter
    mapping is intentionally not extended to double letters (AA, AB, ...).
    """
    output = io.BytesIO()
    if df is None:
        df = pd.DataFrame()

    # Prefer openpyxl because it is already used by pandas for Excel input,
    # so no extra dependency is pulled in just for writing.
    try:
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Stundenplan")
            worksheet = writer.sheets["Stundenplan"]
            for idx, col in enumerate(df.columns, start=1):
                max_len = max(df[col].astype(str).map(len).max() if not df.empty else 0, len(str(col))) + 2
                col_letter = chr(64 + idx) if idx <= 26 else None
                if col_letter:
                    worksheet.column_dimensions[col_letter].width = min(max_len, 80)
    except Exception as e:
        # This catches failures anywhere in the block above, not just the
        # column-width tuning - including df.to_excel() itself. Falling
        # back to a plain, unstyled write is deliberate (a working
        # spreadsheet with default column widths beats no file at all), but
        # doing so completely silently would hide a real bug in the primary
        # path forever - it's worth a log line even though the user still
        # gets a usable file either way.
        logger.warning(f"openpyxl-based Excel export failed, falling back to a plain writer: {e}")
        output = io.BytesIO()
        with pd.ExcelWriter(output) as writer:
            df.to_excel(writer, index=False, sheet_name="Stundenplan")

    processed_data = output.getvalue()
    return processed_data


def generate_ics_download(
    schedule_data: Iterable,
    calendar_name: str = "ZHAW Planner",
    fallback_date: date | None = None,
) -> bytes:
    """
    Create an ICS calendar payload from the currently selected modules.

    Every module produces exactly one VEVENT (one Excel row = one concrete
    session), so nothing selected by the student silently disappears from
    the exported calendar:
      - Modules with a `datum` become a timed event on that exact date.
      - Modules without a `datum` (a data gap in the source Excel, since a
        specific date is expected per row) still become a calendar entry -
        an all-day placeholder on `fallback_date`, clearly flagged in the
        title/description so it isn't mistaken for a confirmed time.

    Exams (`ist_pruefung`) are marked in the title, tagged with
    CATEGORIES:PRUEFUNG and get two reminders (1 day + 2 hours before);
    regular sessions get no VALARM so the calendar app's own default
    reminder applies instead of stacking notifications on top of it.

    Events are emitted in chronological order and tagged with the course
    code as an extra category so calendar apps that support per-category
    colors (Outlook, Apple Calendar) can auto-color by course.
    """
    modules = list(schedule_data)

    def _sort_key(m: Any) -> tuple:
        sort_date = getattr(m, "datum", None) or fallback_date or date.max
        sort_time = getattr(m, "startzeit", None) or time.min
        return (sort_date, sort_time)

    modules.sort(key=_sort_key)

    header_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ZHAW Planner//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape_ics_text(calendar_name)}",
        "X-WR-TIMEZONE:Europe/Zurich",
        f"X-WR-CALDESC:{_escape_ics_text('Persoenlicher Stundenplan-Export aus dem ZHAW MSc Psychology Planer.')}",
    ]
    lines = [_fold_ics_line(entry) for entry in header_lines]

    now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    anchor_date = fallback_date or date.today()
    used_uids: dict[str, int] = {}

    for module in modules:
        start_time: time | None = getattr(module, "startzeit", None)
        end_time: time | None = getattr(module, "endzeit", None)
        if start_time is None or end_time is None:
            continue

        module_date: date | None = getattr(module, "datum", None)
        has_date = module_date is not None
        is_exam = bool(getattr(module, "ist_pruefung", False))

        location = _clean_field(getattr(module, "raum", None)) or ""
        summary = _event_summary(module, has_date)
        description = _event_description(module, has_date)

        # Content-based UID (course + date + time) instead of a raw counter,
        # so re-exporting the same selection updates existing calendar
        # entries on re-import instead of creating duplicates.
        uid_key = f"{_uid_base(module)}-{(module_date or anchor_date).strftime('%Y%m%d')}-{start_time.strftime('%H%M')}"
        occurrence = used_uids.get(uid_key, 0)
        used_uids[uid_key] = occurrence + 1
        uid = f"zhaw-{uid_key}{f'-{occurrence}' if occurrence else ''}@zhaw-planner"

        event_lines = ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{now_utc}", "SEQUENCE:0"]

        if has_date:
            dt_start_utc = _zurich_to_utc(datetime.combine(module_date, start_time))
            dt_end_utc = _zurich_to_utc(datetime.combine(module_date, end_time))
            event_lines.extend(
                [
                    f"DTSTART:{dt_start_utc.strftime('%Y%m%dT%H%M%SZ')}",
                    f"DTEND:{dt_end_utc.strftime('%Y%m%dT%H%M%SZ')}",
                    "TRANSP:OPAQUE",
                ]
            )
        else:
            # No usable date from the source data: keep the module visible
            # as an all-day placeholder instead of dropping it silently.
            # TRANSPARENT so it doesn't visually block the whole day.
            event_lines.extend(
                [
                    f"DTSTART;VALUE=DATE:{anchor_date.strftime('%Y%m%d')}",
                    f"DTEND;VALUE=DATE:{(anchor_date + timedelta(days=1)).strftime('%Y%m%d')}",
                    "TRANSP:TRANSPARENT",
                ]
            )

        categories = ["PRUEFUNG" if is_exam else "LEHRVERANSTALTUNG"]
        course_tag = _clean_field(getattr(module, "kurs_nr", None)) or _clean_field(getattr(module, "modul_nr", None))
        if course_tag:
            categories.append(course_tag)

        event_lines.extend(
            [
                f"SUMMARY:{_escape_ics_text(summary)}",
                f"LOCATION:{_escape_ics_text(location)}",
                f"DESCRIPTION:{_escape_ics_text(description)}",
                f"CATEGORIES:{','.join(_escape_ics_text(c) for c in categories)}",
            ]
        )

        if is_exam:
            event_lines.append("PRIORITY:1")
            for trigger in ("-P1D", "-PT2H"):
                event_lines.extend(
                    [
                        "BEGIN:VALARM",
                        "ACTION:DISPLAY",
                        f"DESCRIPTION:{_escape_ics_text(summary)}",
                        f"TRIGGER:{trigger}",
                        "END:VALARM",
                    ]
                )

        event_lines.append("END:VEVENT")
        lines.extend(_fold_ics_line(entry) for entry in event_lines)

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines).encode("utf-8")