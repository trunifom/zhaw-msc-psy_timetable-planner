"""
ZHAW MSc Psychology - Timetable Planner (Presentation Layer)
Author: HealthData CodeArchitect
Description: Advanced Streamlit GUI focusing on state-of-the-art UI/UX, 
robust error handling, and separation of concerns.
"""

import streamlit as st
import pandas as pd
from typing import List, Tuple, Any
from datetime import date, timedelta
import re
import plotly.express as px
from i18n import get_text

try:
    from data_loader import load_schedule_from_dataframe, DataLoaderError
    from scheduler import find_time_conflicts
    from models import ZHAWModule
    # NEU: Export-Funktionen hier in den Try-Block aufnehmen
    from export import prepare_timetable_for_export, generate_excel_download, generate_ics_download
    MODULES_AVAILABLE = True
except ImportError as e:
    MODULES_AVAILABLE = False
    st.error(get_text("de", "system.backend_missing", error=e))


# ==========================================
# 1. PAGE CONFIGURATION & CUSTOM STYLING
# ==========================================
st.set_page_config(
    page_title=get_text("de", "app.page_title"),
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Optional: Inject minimal custom CSS for cleaner metric cards and dataframe styling
st.markdown("""
    <style>
    .stApp {
        background: #0f1117;
        color: #eaeef7;
    }
    .stMetric {
        background: #171b26;
        color: #eaeef7;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.08);
        box-shadow: 0 8px 24px rgba(0,0,0,0.18);
    }
    .stMetric label, .stMetric [data-testid="stMetricLabel"], .stMetric [data-testid="stMetricDelta"], .stMetric [data-testid="stMetricValue"] {
        color: #eaeef7 !important;
    }
    div[data-testid="stTabs"] button {
        color: #d7def0 !important;
    }
    div[data-testid="stTabs"] button[aria-selected="true"] {
        color: #ffffff !important;
    }
    .stDataFrame, .stDataEditor {
        border-radius: 12px;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. SESSION STATE INITIALIZATION
# ==========================================
def init_session_state() -> None:
    """Initializes default variables in Streamlit's session state."""
    if 'raw_data' not in st.session_state:
        st.session_state.raw_data = None
    if 'processed_modules' not in st.session_state:
        st.session_state.processed_modules = []
    if 'conflicts' not in st.session_state:
        st.session_state.conflicts = []
    if 'planning_finalized' not in st.session_state:
        st.session_state.planning_finalized = False
    if 'selected_modules' not in st.session_state:
        st.session_state.selected_modules = []
    if 'filters_initialized' not in st.session_state:
        st.session_state.filters_initialized = False
    if 'selected_course_bases' not in st.session_state:
        st.session_state.selected_course_bases = []
    if 'ui_language' not in st.session_state:
        st.session_state.ui_language = "de"


def t(key: str, **kwargs: object) -> str:
    """Translate a UI label using session language with DE fallback."""
    return get_text(st.session_state.get("ui_language", "de"), key, **kwargs)


def c(key: str) -> str:
    """Translate a dataframe column label via i18n."""
    return t(f"col.{key}")

init_session_state()

# ==========================================
# 3. HELPER FUNCTIONS (UI LOGIC)
# ==========================================
def handle_file_upload(uploaded_file: Any) -> None:
    """
    Handles the parsing of the uploaded file with comprehensive error handling.
    Supports CSV and Excel files.
    """
    try:
        # Determine file type and parse accordingly
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
            st.session_state.raw_data = df
            st.session_state.processed_modules = load_schedule_from_dataframe(df)
            st.session_state.conflicts = find_time_conflicts(st.session_state.processed_modules)
            st.session_state.selected_modules = []
            st.session_state.selected_course_bases = []
            st.toast(t("upload.success"), icon="✅")
            return
        elif uploaded_file.name.endswith(('.xls', '.xlsx')):
            xls = pd.ExcelFile(uploaded_file)
            last_error: Exception | None = None

            for sheet_name in xls.sheet_names:
                candidate_df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                if candidate_df.empty:
                    continue

                try:
                    processed_modules = load_schedule_from_dataframe(candidate_df)
                except Exception as err:
                    last_error = err
                    continue

                st.session_state.raw_data = candidate_df
                st.session_state.processed_modules = processed_modules
                st.session_state.conflicts = find_time_conflicts(st.session_state.processed_modules)
                st.session_state.selected_modules = []
                st.session_state.selected_course_bases = []
                st.toast(t("upload.success_sheet", sheet_name=sheet_name), icon="✅")
                return

            # No sheet could be parsed into the required schema.
            if last_error is not None:
                raise last_error
            raise DataLoaderError(t("upload.no_sheet"))
        else:
            st.error(t("upload.unsupported"))
            return

    except ValueError as ve:
        # Catch specific Pydantic validation errors from the data layer
        st.error(t("upload.validation_error", error=ve))
        st.info(t("upload.validation_hint"))
    except Exception as e:
        # Catch unforeseen errors (e.g., corrupted file)
        st.error(t("upload.unexpected_error", error=e))


def render_export_section(modules: List) -> None:
    """
    Renders the download button and handles the export logic pipeline.
    Transforms module objects to dataframe, then serializes to Excel.
    """
    if not modules:
        return  # Nichts anzeigen, wenn noch keine Daten da sind

    st.subheader(t("export.subheader"))

    st.session_state.planning_finalized = st.checkbox(
        t("export.finalize_checkbox"),
        value=st.session_state.planning_finalized,
        help=t("export.finalize_help"),
    )

    if not st.session_state.planning_finalized:
        st.info(t("export.locked_info"))
        return
    
    try:
        with st.spinner(t("export.spinner")):
            # 1. Daten über die Business-Logik (export.py) transformieren
            export_data = prepare_timetable_for_export(modules)
            
            # 2. Binären Excel-Stream generieren
            excel_bytes = generate_excel_download(export_data)
            ics_bytes = generate_ics_download(modules, calendar_name=t("export.calendar_name"))
            
            # 3. Streamlit Download-Widget rendern
            st.download_button(
                label=t("export.download_excel"),
                data=excel_bytes,
                file_name="ZHAW_Planner_Export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help=t("export.download_excel_help")
            )

            st.download_button(
                label=t("export.download_ics"),
                data=ics_bytes,
                file_name="ZHAW_Planner_Export.ics",
                mime="text/calendar",
                help=t("export.download_ics_help"),
            )

            modules_with_date = sum(1 for m in modules if getattr(m, "datum", None) is not None)
            if modules_with_date < len(modules):
                st.caption(
                    t("export.ics_missing_dates", count=(len(modules) - modules_with_date))
                )
    except Exception as e:
        st.error(t("export.error", error=e))


def _weekday_label(module: Any) -> str:
    value = getattr(module.wochentag, "value", module.wochentag)
    normalized = str(value).strip().lower()
    translated = t(f"weekday.{normalized}")
    if translated.startswith("weekday."):
        return str(value).capitalize()
    return translated


def _weekday_key(module: Any) -> str:
    """Return canonical weekday key (language independent)."""
    value = getattr(module.wochentag, "value", module.wochentag)
    return str(value).strip().lower()


def _weekday_labels_in_order() -> list[str]:
    return [
        t("weekday.montag"),
        t("weekday.dienstag"),
        t("weekday.mittwoch"),
        t("weekday.donnerstag"),
        t("weekday.freitag"),
        t("weekday.samstag"),
        t("weekday.sonntag"),
    ]


def _weekday_keys_in_order() -> list[str]:
    return ["montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag"]


def _blocking_weekday_labels() -> list[str]:
    """Weekdays shown in the blocked-days selector; weekends remain supported internally."""
    return _weekday_labels_in_order()[:5]


def _blocking_weekday_keys() -> list[str]:
    """Weekday keys shown in blocked-days selector; weekends remain supported internally."""
    return _weekday_keys_in_order()[:5]


def _semester_date_bounds(modules: List[Any]) -> tuple[date | None, date | None]:
    """Return first and last dated schedule entry for semester-bound validations."""
    dates = sorted({m.datum for m in modules if getattr(m, "datum", None) is not None})
    if not dates:
        return (None, None)
    return (dates[0], dates[-1])


def _default_absence_end(start_value: date, max_value: date | None) -> date:
    """Prefer the following day as default end date, capped by semester max date."""
    candidate = start_value + timedelta(days=1)
    if max_value is not None and candidate > max_value:
        return max_value
    return candidate


def _absence_settings() -> dict[str, Any]:
    """Normalized absence settings persisted from guided planning widgets."""
    raw_blocked_days = st.session_state.get("absence_blocked_days_values", []) or []
    normalized_blocked_days: set[str] = set()
    for day in raw_blocked_days:
        token = str(day).strip().lower()
        if token in _weekday_keys_in_order():
            normalized_blocked_days.add(token)
            continue
        for key in _weekday_keys_in_order():
            if token == t(f"weekday.{key}").strip().lower():
                normalized_blocked_days.add(key)
                break

    return {
        "period_enabled": bool(st.session_state.get("absence_period_enabled", False)),
        "period_start": st.session_state.get("absence_period_start"),
        "period_end": st.session_state.get("absence_period_end"),
        "dates_enabled": bool(st.session_state.get("absence_dates_enabled", False)),
        "dates": set(st.session_state.get("absence_dates_values", []) or []),
        "blocked_enabled": bool(st.session_state.get("absence_blocked_enabled", False)),
        "blocked_days": normalized_blocked_days,
        "blocked_halfday": st.session_state.get("absence_blocked_halfday_value", t("guided.full_day")),
    }


def _absence_rules_summary(settings: dict[str, Any]) -> list[str]:
    """Human-readable summary of active absence constraints."""
    rules: list[str] = []

    if settings["period_enabled"] and settings["period_start"] and settings["period_end"]:
        rules.append(
            t(
                "dashboard.absence.period",
                start=settings["period_start"].strftime("%d.%m.%Y"),
                end=settings["period_end"].strftime("%d.%m.%Y"),
            )
        )

    if settings["dates_enabled"] and settings["dates"]:
        sorted_dates = sorted(settings["dates"])
        shown = ", ".join(d.strftime("%d.%m.%Y") for d in sorted_dates[:5])
        suffix = " ..." if len(sorted_dates) > 5 else ""
        rules.append(t("dashboard.absence.dates", dates=f"{shown}{suffix}"))

    if settings["blocked_enabled"] and settings["blocked_days"]:
        days = ", ".join(t(f"weekday.{d}") for d in sorted(settings["blocked_days"]))
        rules.append(
            t(
                "dashboard.absence.blocked_days",
                days=days,
                halfday=settings["blocked_halfday"],
            )
        )

    return rules


def _absence_reasons_for_module(module: Any, settings: dict[str, Any]) -> list[str]:
    """Return all matching absence reasons for a module row."""
    reasons: list[str] = []
    datum_value = getattr(module, "datum", None)
    day_key = _weekday_key(module)

    if settings["period_enabled"] and settings["period_start"] and settings["period_end"] and datum_value is not None:
        if settings["period_start"] <= datum_value <= settings["period_end"]:
            reasons.append(t("absence.reason.period"))

    if settings["dates_enabled"] and datum_value in settings["dates"]:
        reasons.append(t("absence.reason.date"))

    if settings["blocked_enabled"] and day_key in settings["blocked_days"] and _matches_halfday(module, settings["blocked_halfday"]):
        reasons.append(t("absence.reason.weekday_halfday", halfday=settings["blocked_halfday"]))

    return reasons


def _absence_conflict_dataframe(modules: List[Any], settings: dict[str, Any]) -> pd.DataFrame:
    """Build table rows for modules violating active absence constraints."""
    if not modules:
        return pd.DataFrame()

    rows = []
    for module in modules:
        reasons = _absence_reasons_for_module(module, settings)
        if not reasons:
            continue
        rows.append(
            {
                c("date"): _conflict_date_label(module),
                c("weekday"): _weekday_label(module),
                c("module"): _module_label(module),
                c("time"): f"{module.startzeit.strftime('%H:%M')} - {module.endzeit.strftime('%H:%M')}",
                c("reason"): ", ".join(reasons),
            }
        )

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values([c("date"), c("weekday"), c("time")], ascending=[True, True, True])


def _absence_course_impact_dataframe(modules: List[Any], settings: dict[str, Any]) -> pd.DataFrame:
    """Summarize absence impact per base course including absence percentages."""
    if not modules:
        return pd.DataFrame()

    totals: dict[str, dict[str, Any]] = {}
    for module in modules:
        key = _module_group_title(module)
        if key not in totals:
            totals[key] = {
                c("base_course"): key,
                c("rows"): 0,
                c("absence_rows"): 0,
                c("absence_pct"): 0.0,
                c("attendance_req_pct"): None,
                c("allowed_absence_pct"): None,
                c("risk_status"): t("absence.risk.unknown"),
            }

        totals[key][c("rows")] += 1
        if _absence_reasons_for_module(module, settings):
            totals[key][c("absence_rows")] += 1

        raw_req = getattr(module, "anwesenheitspflicht_prozent", None)
        if raw_req is not None and totals[key][c("attendance_req_pct")] is None:
            try:
                totals[key][c("attendance_req_pct")] = float(raw_req)
            except Exception:
                pass

    rows = []
    for row in totals.values():
        total = max(1, int(row[c("rows")]))
        impacted = int(row[c("absence_rows")])
        absence_pct = round((impacted / total) * 100.0, 1)
        row[c("absence_pct")] = absence_pct

        req = row[c("attendance_req_pct")]
        if req is None:
            row[c("allowed_absence_pct")] = None
            row[c("risk_status")] = t("absence.risk.unknown")
        else:
            allowed = max(0.0, min(100.0, 100.0 - float(req)))
            row[c("allowed_absence_pct")] = round(allowed, 1)
            row[c("risk_status")] = t("absence.risk.high") if absence_pct > allowed else t("absence.risk.ok")

        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values([c("absence_pct"), c("absence_rows"), c("base_course")], ascending=[False, False, True])


def _style_absence_rows(df: pd.DataFrame, reason_col: str) -> Any:
    """Style rows to highlight absence-related violations."""
    def _row_style(row: pd.Series) -> list[str]:
        has_reason = bool(str(row.get(reason_col, "")).strip())
        if has_reason:
            return ["background-color: rgba(220, 38, 38, 0.24)"] * len(row)
        return [""] * len(row)

    return df.style.apply(_row_style, axis=1)


def _style_risk_rows(df: pd.DataFrame) -> Any:
    """Style course impact table by risk status."""
    status_col = c("risk_status")

    def _row_style(row: pd.Series) -> list[str]:
        status = str(row.get(status_col, ""))
        if status == t("absence.risk.high"):
            return ["background-color: rgba(220, 38, 38, 0.24)"] * len(row)
        if status == t("absence.risk.ok"):
            return ["background-color: rgba(34, 197, 94, 0.18)"] * len(row)
        return ["background-color: rgba(234, 179, 8, 0.14)"] * len(row)

    return df.style.apply(_row_style, axis=1)


def _absence_overlay_for_week(settings: dict[str, Any]) -> pd.DataFrame:
    """Create overlay rows for blocked weekdays in weekly timeline chart."""
    if not settings.get("blocked_enabled") or not settings.get("blocked_days"):
        return pd.DataFrame()

    halfday = settings.get("blocked_halfday", t("guided.full_day"))
    if halfday == t("guided.morning"):
        start = "00:00:00"
        end = "12:00:00"
    elif halfday == t("guided.afternoon"):
        start = "12:00:00"
        end = "23:59:00"
    else:
        start = "00:00:00"
        end = "23:59:00"

    rows = []
    for day_key in sorted(settings.get("blocked_days", []), key=lambda d: _weekday_keys_in_order().index(d) if d in _weekday_keys_in_order() else 99):
        rows.append(
            {
                c("weekday"): t(f"weekday.{day_key}"),
                c("module"): t("timetable.absence_overlay_label"),
                c("start"): pd.to_datetime(f"1970-01-01 {start}"),
                c("end"): pd.to_datetime(f"1970-01-01 {end}"),
                c("type"): t("timetable.absence_overlay_type"),
            }
        )
    return pd.DataFrame(rows)


def _lessons_per_week(modules: List[Any]) -> tuple[float, float, int]:
    """Return lessons/week based on recurring rows + average dated week load."""
    if not modules:
        return (0.0, 0.0, 0)

    undated_minutes = sum(m.duration_minutes for m in modules if getattr(m, "datum", None) is None)

    dated_rows = []
    for module in modules:
        datum_value = getattr(module, "datum", None)
        if datum_value is None:
            continue
        iso = datum_value.isocalendar()
        dated_rows.append({"year": iso.year, "week": iso.week, "minutes": module.duration_minutes})

    avg_dated_week_minutes = 0.0
    observed_weeks = 0
    if dated_rows:
        dated_df = pd.DataFrame(dated_rows)
        weekly = dated_df.groupby(["year", "week"], as_index=False)["minutes"].sum()
        avg_dated_week_minutes = float(weekly["minutes"].mean())
        observed_weeks = int(len(weekly))

    total_week_minutes = undated_minutes + avg_dated_week_minutes
    lessons = round(total_week_minutes / 45.0, 1)
    hours = round(total_week_minutes / 60.0, 1)
    return (lessons, hours, observed_weeks)


def _matches_halfday(module: Any, halfday: str) -> bool:
    start_hour = module.startzeit.hour
    if halfday == t("guided.full_day"):
        return True
    if halfday == t("guided.morning"):
        return start_hour < 12
    if halfday == t("guided.afternoon"):
        return start_hour >= 12
    return False


def _module_to_row(module: Any, module_id: int, selected: bool) -> dict:
    datum_value = getattr(module, "datum", None)
    return {
        c("select"): selected,
        c("id"): module_id,
        c("module_no"): getattr(module, "modul_nr", None) or "",
        c("course_no"): getattr(module, "kurs_nr", None) or "",
        c("module"): module.modulname,
        c("weekday"): _weekday_label(module),
        c("date"): datum_value.strftime("%Y-%m-%d") if datum_value else "",
        c("start"): module.startzeit.strftime("%H:%M"),
        c("end"): module.endzeit.strftime("%H:%M"),
        c("exam"): t("guided.yes") if getattr(module, "ist_pruefung", False) else t("guided.no"),
        c("type"): module.modultyp,
        c("lecturers"): module.dozierende,
        c("ects"): module.ects,
    }


def _split_course_variant(course_name: str) -> tuple[str, str, bool]:
    """Split course title into base title and variant suffix (group/run/exam)."""
    raw = str(course_name or "").strip()
    if not raw:
        return ("Unbekannter Kurs", "", False)

    name = raw
    variant_parts: list[str] = []
    is_exam = False

    exam_pattern = r"\s*[/\-]\s*pr(?:u|ue|uef|uf|uef|ü)fung\s*$"
    if re.search(exam_pattern, name, flags=re.IGNORECASE):
        is_exam = True
        variant_parts.append("PRUEFUNG")
        name = re.sub(exam_pattern, "", name, flags=re.IGNORECASE).strip()

    variant_pattern = (
        r"\s*[/\-]\s*("
        r"ganzklasse|"
        r"gruppe\s+[a-z0-9][a-z0-9\s&+\-]*|"
        r"tk\d+\s+gruppe\s+[a-z](?:\s*&\s*gruppe\s*[a-z])?|"
        r"durchf(?:u|ue|ü)hrung\s*\d+"
        r")\s*$"
    )
    while True:
        match = re.search(variant_pattern, name, flags=re.IGNORECASE)
        if not match:
            break
        variant_text = match.group(1).strip()
        variant_parts.insert(0, variant_text.upper())
        name = re.sub(variant_pattern, "", name, count=1, flags=re.IGNORECASE).strip()

    base = name.strip("-/ ") or raw
    variant = " | ".join(variant_parts)
    return (base, variant, is_exam)


def _module_group_key(module: Any) -> str:
    """Return stable module-group key: prefer Modul-Nr, fallback to normalized base title."""
    modul_nr = str(getattr(module, "modul_nr", "") or "").strip()
    if modul_nr:
        return modul_nr
    base, _, _ = _split_course_variant(module.modulname)
    return f"BASIS::{base.lower()}"


def _module_group_display(module_key: str, modules: List[Any]) -> str:
    """Human-readable group label for module-level selection."""
    if module_key.startswith("BASIS::"):
        base, _, _ = _split_course_variant(modules[0].modulname)
        return base
    base, _, _ = _split_course_variant(modules[0].modulname)
    return f"{module_key} - {base}"


def _module_variant_label(module: Any) -> str:
    """Return normalized variant label for selection logic."""
    _, variant, _ = _split_course_variant(module.modulname)
    return variant or "STANDARD"


def _module_course_family_key(module: Any) -> str:
    """Return grouping key for course parts inside one module."""
    kurs_nr = str(getattr(module, "kurs_nr", "") or "").strip()
    if kurs_nr:
        return kurs_nr
    base, _, _ = _split_course_variant(module.modulname)
    return f"BASIS::{base}"


def _module_label(module: Any) -> str:
    """Human-readable label used in charts and tables."""
    modul_nr = str(getattr(module, "modul_nr", "") or "").strip()
    kurs_nr = str(getattr(module, "kurs_nr", "") or "").strip()
    base = str(getattr(module, "modulname", "") or "").strip()
    if modul_nr and kurs_nr:
        return f"{modul_nr} / {kurs_nr} - {base}"
    if modul_nr:
        return f"{modul_nr} - {base}"
    if kurs_nr:
        return f"{kurs_nr} - {base}"
    return base


def _module_to_ui_row(module: Any) -> dict:
    """Localized row representation for selected module tables."""
    datum_value = getattr(module, "datum", None)
    return {
        c("module_no"): getattr(module, "modul_nr", None) or "",
        c("course_no"): getattr(module, "kurs_nr", None) or "",
        c("module"): module.modulname,
        c("weekday"): _weekday_label(module),
        c("date"): datum_value.strftime("%Y-%m-%d") if datum_value else "",
        c("time"): f"{module.startzeit.strftime('%H:%M')} - {module.endzeit.strftime('%H:%M')}",
        c("duration_min"): module.duration_minutes,
        c("ects"): module.ects,
        c("exam"): t("guided.yes") if getattr(module, "ist_pruefung", False) else t("guided.no"),
        c("lecturers"): module.dozierende,
        c("room"): module.raum,
        c("type"): module.modultyp,
    }


def _module_group_title(module: Any) -> str:
    modul_nr = str(getattr(module, "modul_nr", "") or "").strip()
    if modul_nr:
        return modul_nr
    base, _, _ = _split_course_variant(module.modulname)
    return base


def _module_signature(module: Any) -> tuple:
    """Semantic signature used to suppress exact duplicates."""
    return (
        getattr(module, "datum", None),
        _weekday_label(module),
        module.startzeit.strftime("%H:%M"),
        module.endzeit.strftime("%H:%M"),
        str(getattr(module, "modul_nr", "") or "").strip(),
        str(getattr(module, "kurs_nr", "") or "").strip(),
        str(getattr(module, "modulname", "") or "").strip(),
        str(getattr(module, "raum", "") or "").strip(),
    )


def _same_occurrence_context(left: Any, right: Any) -> bool:
    """True when two rows belong to the same actual occurrence context."""
    left_date = getattr(left, "datum", None)
    right_date = getattr(right, "datum", None)
    if left_date is not None and right_date is not None:
        return left_date == right_date
    return _weekday_label(left) == _weekday_label(right)


def _conflict_date_label(module: Any) -> str:
    datum_value = getattr(module, "datum", None)
    if datum_value is None:
        return t("common.unknown_date")
    return datum_value.strftime("%Y-%m-%d")


def _minutes_overlap(left: Any, right: Any) -> int:
    """Return overlap in minutes for two modules on the same weekday."""
    left_start = left.startzeit.hour * 60 + left.startzeit.minute
    left_end = left.endzeit.hour * 60 + left.endzeit.minute
    right_start = right.startzeit.hour * 60 + right.startzeit.minute
    right_end = right.endzeit.hour * 60 + right.endzeit.minute
    overlap = min(left_end, right_end) - max(left_start, right_start)
    return max(0, overlap)


def _calculate_overlap_rows(modules: List[Any]) -> List[dict]:
    """Build pairwise overlap rows for tables and charts."""
    rows: List[dict] = []
    seen_pairs: set[tuple[tuple, tuple]] = set()
    for i, left in enumerate(modules):
        for right in modules[i + 1 :]:
            if not _same_occurrence_context(left, right):
                continue
            left_signature = _module_signature(left)
            right_signature = _module_signature(right)
            if left_signature == right_signature:
                continue
            overlap = _minutes_overlap(left, right)
            if overlap <= 0:
                continue

            pair_key = tuple(sorted((left_signature, right_signature)))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            left_duration = max(1, left.duration_minutes)
            right_duration = max(1, right.duration_minutes)
            rows.append(
                {
                    c("date"): _conflict_date_label(left),
                    c("module_1"): _module_label(left),
                    c("module_2"): _module_label(right),
                    c("weekday"): _weekday_label(left),
                    c("overlap_min"): overlap,
                    c("overlap_pct_module_1"): round((overlap / left_duration) * 100, 1),
                    c("overlap_pct_module_2"): round((overlap / right_duration) * 100, 1),
                    c("start_1"): left.startzeit.strftime("%H:%M"),
                    c("end_1"): left.endzeit.strftime("%H:%M"),
                    c("start_2"): right.startzeit.strftime("%H:%M"),
                    c("end_2"): right.endzeit.strftime("%H:%M"),
                }
            )
    return rows


def _calculate_module_overlap_summary(modules: List[Any]) -> pd.DataFrame:
    """Summarize how much each module overlaps with others."""
    if not modules:
        return pd.DataFrame()

    totals = {id(module): 0 for module in modules}
    seen_pairs: set[tuple[tuple, tuple]] = set()
    for i, left in enumerate(modules):
        for right in modules[i + 1 :]:
            if not _same_occurrence_context(left, right):
                continue
            left_signature = _module_signature(left)
            right_signature = _module_signature(right)
            if left_signature == right_signature:
                continue
            overlap = _minutes_overlap(left, right)
            if overlap <= 0:
                continue
            pair_key = tuple(sorted((left_signature, right_signature)))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            totals[id(left)] += overlap
            totals[id(right)] += overlap

    summary_rows = []
    for module in modules:
        overlap_total = totals[id(module)]
        duration = max(1, module.duration_minutes)
        summary_rows.append(
            {
                c("module"): _module_label(module),
                c("base_course"): _module_group_title(module),
                c("weekday"): _weekday_label(module),
                c("duration_min"): module.duration_minutes,
                c("overlap_total_min"): overlap_total,
                c("overlap_pct"): round((overlap_total / duration) * 100, 1),
            }
        )

    df = pd.DataFrame(summary_rows)
    if not df.empty:
        df = df.sort_values([c("overlap_total_min"), c("module")], ascending=[False, True])
    return df


def _summarize_conflicts(conflicts: List[Tuple[Any, Any]]) -> pd.DataFrame:
    """Aggregate detailed conflicts into course-pair summaries."""
    if not conflicts:
        return pd.DataFrame()

    summary: dict[tuple[str, str], dict[str, Any]] = {}
    for left, right in conflicts:
        labels = sorted([_module_label(left), _module_label(right)])
        key = (labels[0], labels[1])
        overlap = _minutes_overlap(left, right)
        day_label = _weekday_label(left)
        date_label = _conflict_date_label(left)

        if key not in summary:
            summary[key] = {
                c("module_1"): labels[0],
                c("module_2"): labels[1],
                c("conflict_days_count"): 0,
                c("overlap_total_min"): 0,
                c("conflict_dates"): [],
                c("conflict_weekdays"): [],
            }

        summary[key][c("conflict_days_count")] += 1
        summary[key][c("overlap_total_min")] += overlap
        summary[key][c("conflict_dates")].append(date_label)
        summary[key][c("conflict_weekdays")].append(day_label)

    rows = []
    for data in summary.values():
        rows.append(
            {
                c("module_1"): data[c("module_1")],
                c("module_2"): data[c("module_2")],
                c("conflict_days_count"): data[c("conflict_days_count")],
                c("overlap_total_min"): data[c("overlap_total_min")],
                c("conflict_dates"): ", ".join(sorted(set(data[c("conflict_dates")]))[:6]),
                c("conflict_weekdays"): ", ".join(sorted(set(data[c("conflict_weekdays")]))),
            }
        )

    return pd.DataFrame(rows).sort_values([c("overlap_total_min"), c("conflict_days_count")], ascending=[False, False])


def _semester_timeline_figure(modules: List[Any]):
    """Show all dated lessons over the full semester timeline."""
    rows = []
    for module in modules:
        datum_value = getattr(module, "datum", None)
        if datum_value is None:
            continue
        rows.append(
            {
                c("module"): _module_label(module),
                c("start_datetime"): pd.to_datetime(f"{datum_value.isoformat()} {module.startzeit.strftime('%H:%M:%S')}"),
                c("end_datetime"): pd.to_datetime(f"{datum_value.isoformat()} {module.endzeit.strftime('%H:%M:%S')}"),
                c("weekday"): _weekday_label(module),
                c("type"): module.modultyp,
            }
        )

    if not rows:
        return None

    df = pd.DataFrame(rows)
    fig = px.timeline(
        df,
        x_start=c("start_datetime"),
        x_end=c("end_datetime"),
        y=c("weekday"),
        color=c("module"),
        hover_name=c("module"),
        hover_data={c("type"): True},
        category_orders={c("weekday"): _weekday_labels_in_order()},
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        height=560,
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis_title=t("chart.xaxis_semester"),
        yaxis_title="",
        legend_title_text=t("chart.legend_modules"),
    )
    return fig


def _daily_load_figure(modules: List[Any]):
    """Show total scheduled minutes per date across the semester."""
    rows = []
    for module in modules:
        datum_value = getattr(module, "datum", None)
        if datum_value is None:
            continue
        rows.append({c("date"): datum_value, c("duration_min"): module.duration_minutes, c("module"): _module_label(module)})

    if not rows:
        return None

    df = pd.DataFrame(rows)
    daily = df.groupby(c("date"), as_index=False)[c("duration_min")].sum()
    fig = px.bar(daily, x=c("date"), y=c("duration_min"), title=t("chart.daily_load_title"))
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=40, b=10), yaxis_title=t("chart.yaxis_minutes"), xaxis_title=t("chart.xaxis_semester"))
    return fig


def _calculate_exam_feasibility(modules: List[Any]) -> pd.DataFrame:
    """Check whether exam rows overlap with other selected modules on the same date."""
    exam_rows = []
    exam_modules = [m for m in modules if getattr(m, "ist_pruefung", False)]
    normal_modules = [m for m in modules if not getattr(m, "ist_pruefung", False)]

    for exam in exam_modules:
        conflict_count = 0
        if getattr(exam, "datum", None) is not None:
            for other in normal_modules:
                if getattr(other, "datum", None) != exam.datum:
                    continue
                if _minutes_overlap(exam, other) > 0:
                    conflict_count += 1

        if getattr(exam, "datum", None) is None:
            status = t("exam.status_unknown")
        elif conflict_count == 0:
            status = t("exam.status_ok")
        else:
            status = t("exam.status_conflict")

        exam_rows.append(
            {
                c("exam_name"): _module_label(exam),
                c("module"): _module_group_title(exam),
                c("date"): exam.datum.strftime("%Y-%m-%d") if getattr(exam, "datum", None) else "",
                c("time"): f"{exam.startzeit.strftime('%H:%M')} - {exam.endzeit.strftime('%H:%M')}",
                c("conflicts"): conflict_count,
                c("status"): status,
            }
        )

    return pd.DataFrame(exam_rows)


def _weekly_timeline_figure(modules: List[Any]):
    """Create a weekly timeline chart."""
    if not modules:
        return None

    day_labels = _weekday_labels_in_order()
    day_order = {label: idx for idx, label in enumerate(day_labels)}
    rows = []
    settings = _absence_settings()
    for module in modules:
        rows.append(
            {
                c("weekday"): _weekday_label(module),
                c("module"): _module_label(module),
                c("start"): pd.to_datetime(f"1970-01-01 {module.startzeit.strftime('%H:%M:%S')}"),
                c("end"): pd.to_datetime(f"1970-01-01 {module.endzeit.strftime('%H:%M:%S')}"),
                c("type"): module.modultyp,
            }
        )

    df = pd.DataFrame(rows)
    overlay_df = _absence_overlay_for_week(settings)
    if not overlay_df.empty:
        df = pd.concat([df, overlay_df], ignore_index=True)
    if df.empty:
        return None

    fig = px.timeline(
        df,
        x_start=c("start"),
        x_end=c("end"),
        y=c("weekday"),
        color=c("type"),
        hover_name=c("module"),
        hover_data={c("start"): False, c("end"): False},
        category_orders={c("weekday"): list(day_order.keys())},
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis_title=t("chart.xaxis_time"),
        yaxis_title="",
        legend_title_text=t("chart.legend_module_type"),
    )
    fig.update_xaxes(tickformat="%H:%M")
    return fig


def _weekday_bar_figure(modules: List[Any]):
    if not modules:
        return None
    df = pd.DataFrame({c("weekday"): [_weekday_label(m) for m in modules]})
    order = _weekday_labels_in_order()
    fig = px.bar(df, x=c("weekday"), title=t("chart.weekday_title"), category_orders={c("weekday"): order})
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=40, b=10), yaxis_title=t("chart.yaxis_items"))
    return fig


def _overlap_bar_figure(summary_df: pd.DataFrame):
    if summary_df.empty:
        return None
    top = summary_df.head(12).copy()
    fig = px.bar(
        top,
        x=c("overlap_total_min"),
        y=c("module"),
        orientation="h",
        title=t("chart.overlap_title"),
        color=c("overlap_pct"),
        color_continuous_scale="Reds",
    )
    fig.update_layout(height=max(440, 32 * len(top) + 140), margin=dict(l=10, r=10, t=40, b=10))
    return fig


def render_guided_planning(all_modules: List[Any]) -> List[Any]:
    """Guided, German-first course planning assistant with dynamic questions."""
    st.subheader(t("guided.subheader"))

    if not all_modules:
        st.info(t("guided.no_data"))
        return []

    st.markdown(t("guided.intro"))

    semester_start, semester_end = _semester_date_bounds(all_modules)
    absence_period_valid = True

    with st.container(border=True):
        st.markdown(t("guided.step1"))

        if semester_start and semester_end:
            st.caption(
                t(
                    "guided.semester_range",
                    start=semester_start.strftime("%d.%m.%Y"),
                    end=semester_end.strftime("%d.%m.%Y"),
                )
            )

        has_absence_period = st.radio(
            t("guided.q.absence_period"),
            options=[t("guided.no"), t("guided.yes")],
            horizontal=True,
            key="q_absence_period",
        )

        absence_start = None
        absence_end = None
        if has_absence_period == t("guided.yes"):
            if "absence_start_prev" not in st.session_state:
                st.session_state.absence_start_prev = None

            if semester_start and "absence_start" not in st.session_state:
                st.session_state.absence_start = semester_start

            current_start = st.session_state.get("absence_start") or semester_start or date.today()
            if "absence_end" not in st.session_state:
                st.session_state.absence_end = _default_absence_end(current_start, semester_end)

            col1, col2 = st.columns(2)
            with col1:
                absence_start = st.date_input(
                    t("guided.absence_from"),
                    key="absence_start",
                    min_value=semester_start,
                    max_value=semester_end,
                )

            previous_start = st.session_state.get("absence_start_prev")
            current_end = st.session_state.get("absence_end")
            if previous_start != absence_start and (current_end is None or current_end <= absence_start):
                st.session_state.absence_end = _default_absence_end(absence_start, semester_end)
            st.session_state.absence_start_prev = absence_start

            with col2:
                absence_end = st.date_input(
                    t("guided.absence_to"),
                    key="absence_end",
                    min_value=absence_start or semester_start,
                    max_value=semester_end,
                )

            if absence_start and absence_end and absence_start > absence_end:
                st.error(t("guided.absence_invalid_order"))
                absence_period_valid = False

            if semester_start and semester_end and absence_start and absence_end:
                if absence_start < semester_start or absence_end > semester_end:
                    st.error(
                        t(
                            "guided.absence_out_of_range",
                            start=semester_start.strftime("%d.%m.%Y"),
                            end=semester_end.strftime("%d.%m.%Y"),
                        )
                    )
                    absence_period_valid = False

        st.session_state.absence_period_enabled = has_absence_period == t("guided.yes")
        st.session_state.absence_period_start = absence_start
        st.session_state.absence_period_end = absence_end

        has_absent_dates = st.radio(
            t("guided.q.absent_dates"),
            options=[t("guided.no"), t("guided.yes")],
            horizontal=True,
            key="q_absent_dates",
        )

        absent_dates = []
        if has_absent_dates == t("guided.yes"):
            available_dates = sorted(
                {m.datum for m in all_modules if getattr(m, "datum", None) is not None}
            )
            if available_dates:
                absent_dates = st.multiselect(
                    t("guided.absent_dates_select"),
                    options=available_dates,
                    format_func=lambda d: d.strftime("%d.%m.%Y"),
                    key="absent_dates",
                )
            else:
                st.caption(t("guided.no_dates_found"))

        st.session_state.absence_dates_enabled = has_absent_dates == t("guided.yes")
        st.session_state.absence_dates_values = absent_dates

        has_blocked_days = st.radio(
            t("guided.q.blocked_days"),
            options=[t("guided.no"), t("guided.yes")],
            horizontal=True,
            key="q_blocked_days",
        )

        blocked_days = []
        blocked_halfday = t("guided.full_day")
        if has_blocked_days == t("guided.yes"):
            blocked_days = st.multiselect(
                t("guided.blocked_days"),
                options=_blocking_weekday_keys(),
                format_func=lambda day_key: t(f"weekday.{day_key}"),
                key="blocked_days",
            )
            blocked_halfday = st.selectbox(
                t("guided.blocked_range"),
                options=[t("guided.full_day"), t("guided.morning"), t("guided.afternoon")],
                key="blocked_halfday",
            )

        st.session_state.absence_blocked_enabled = has_blocked_days == t("guided.yes")
        st.session_state.absence_blocked_days_values = blocked_days
        st.session_state.absence_blocked_halfday_value = blocked_halfday

    with st.container(border=True):
        st.markdown(t("guided.step2"))
        modul_nr_search = st.text_input(
            t("guided.search.modul_nr"),
            placeholder=t("guided.search.modul_nr_placeholder"),
            key="filter_modul_nr",
        ).strip().lower()

        kurs_nr_search = st.text_input(
            t("guided.search.kurs_nr"),
            placeholder=t("guided.search.kurs_nr_placeholder"),
            key="filter_kurs_nr",
        ).strip().lower()

        search_text = st.text_input(
            t("guided.search.text"),
            placeholder=t("guided.search.text_placeholder"),
            key="filter_search",
        ).strip().lower()

        base_search_text = st.text_input(
            t("guided.search.base"),
            placeholder=t("guided.search.base_placeholder"),
            key="filter_base_search",
        ).strip().lower()

        module_types = sorted({str(getattr(m, "modultyp", t("common.na"))) for m in all_modules if getattr(m, "modultyp", None)})
        selected_types = st.multiselect(
            t("guided.filter.types"),
            options=module_types,
            key="filter_module_types",
        )

        weekdays_present = sorted({_weekday_label(m) for m in all_modules})
        selected_weekdays = st.multiselect(
            t("guided.filter.weekdays"),
            options=weekdays_present,
            key="filter_weekdays",
        )

        lecturers = sorted(
            {
                str(getattr(m, "dozierende", "N/A"))
                for m in all_modules
                if getattr(m, "dozierende", None)
            }
        )
        selected_lecturers = st.multiselect(
            t("guided.filter.lecturers"),
            options=lecturers,
            key="filter_lecturers",
        )

        sort_mode = st.selectbox(
            t("guided.sort"),
            options=[t("guided.sort.date"), t("guided.sort.weekday"), t("guided.sort.name")],
            key="filter_sort_mode",
        )

    filtered: List[Any] = []
    absent_date_set = set(absent_dates)
    for module in all_modules:
        datum_value = getattr(module, "datum", None)
        day_label = _weekday_label(module)
        modul_nr_value = str(getattr(module, "modul_nr", "") or "").lower()
        kurs_nr_value = str(getattr(module, "kurs_nr", "") or "").lower()

        if modul_nr_search and modul_nr_search not in modul_nr_value:
            continue

        if kurs_nr_search and kurs_nr_search not in kurs_nr_value:
            continue

        if selected_types and str(module.modultyp) not in selected_types:
            continue

        if selected_weekdays and day_label not in selected_weekdays:
            continue

        if selected_lecturers and str(module.dozierende) not in selected_lecturers:
            continue

        if base_search_text:
            base_name, _, _ = _split_course_variant(module.modulname)
            if base_search_text not in base_name.lower():
                continue

        if search_text:
            haystack = " ".join([
                str(module.modulname),
                str(module.dozierende),
                str(module.modultyp),
            ]).lower()
            if search_text not in haystack:
                continue

        filtered.append(module)

    if sort_mode == t("guided.sort.date"):
        filtered.sort(key=lambda m: ((getattr(m, "datum", None) is None), getattr(m, "datum", date.max), m.startzeit))
    elif sort_mode == t("guided.sort.weekday"):
        day_order = {day: idx for idx, day in enumerate(_weekday_labels_in_order())}
        filtered.sort(key=lambda m: (day_order.get(_weekday_label(m), 99), m.startzeit))
    else:
        filtered.sort(key=lambda m: str(m.modulname).lower())

    st.markdown(t("guided.step3_title", count=len(filtered)))
    if not filtered:
        st.warning(t("guided.no_matches"))
        st.session_state.selected_modules = []
        return []

    selection_mode = st.radio(
        t("guided.selection_mode"),
        options=[t("guided.mode.module"), t("guided.mode.course"), t("guided.mode.row")],
        horizontal=True,
        key="selection_mode",
        help=t("guided.selection_mode_help"),
    )

    include_exams = st.checkbox(
        t("guided.include_exams"),
        value=False,
        key="include_exams",
    )

    modules_with_id = list(enumerate(all_modules))
    selected_lookup = {id(m): True for m in st.session_state.get("selected_modules", [])}
    filtered_ids = set(id(m) for m in filtered)

    filtered_with_ids = [(idx, m) for idx, m in modules_with_id if id(m) in filtered_ids]

    if selection_mode == t("guided.mode.module"):
        grouped_modules: dict[str, list[Any]] = {}
        for _, module in filtered_with_ids:
            key = _module_group_key(module)
            grouped_modules.setdefault(key, []).append(module)

        module_rows = []
        selected_keys_prev = set(st.session_state.get("selected_course_bases", []))
        for key, items in sorted(grouped_modules.items(), key=lambda pair: _module_group_display(pair[0], pair[1]).lower()):
            courses = sorted({str(getattr(m, "kurs_nr", "") or "") for m in items if getattr(m, "kurs_nr", None)})
            exam_count = sum(1 for m in items if getattr(m, "ist_pruefung", False))
            dates = sorted({m.datum for m in items if getattr(m, "datum", None) is not None})
            first_date = dates[0].strftime("%Y-%m-%d") if dates else ""
            last_date = dates[-1].strftime("%Y-%m-%d") if dates else ""
            date_range = f"{first_date} - {last_date}" if first_date and last_date else ""
            label = _module_group_display(key, items)
            module_rows.append(
                {
                    c("select"): key in selected_keys_prev,
                    c("module_group"): label,
                    c("module_key"): key,
                    c("courses"): len(courses),
                    c("rows"): len(items),
                    c("exam_dates"): exam_count,
                    c("period"): date_range,
                }
            )

        module_df = pd.DataFrame(module_rows)
        edited_module_df = st.data_editor(
            module_df,
            hide_index=True,
            width="stretch",
            disabled=[c("module_group"), c("module_key"), c("courses"), c("rows"), c("exam_dates"), c("period")],
            column_config={c("select"): st.column_config.CheckboxColumn(c("select"))},
            key="module_group_selector_editor",
        )

        selected_keys = set(edited_module_df.loc[edited_module_df[c("select")] == True, c("module_key")].tolist())
        st.session_state.selected_course_bases = sorted(selected_keys)

        selected_modules = []
        selected_by_module_key: dict[str, list[Any]] = {}
        module_status_rows = []

        st.markdown(t("guided.step4"))

        for key, items in sorted(grouped_modules.items(), key=lambda pair: _module_group_display(pair[0], pair[1]).lower()):
            if key not in selected_keys:
                continue

            label = _module_group_display(key, items)
            non_exam_items = [m for m in items if not getattr(m, "ist_pruefung", False)]
            exam_items = [m for m in items if getattr(m, "ist_pruefung", False)]

            families: dict[str, list[Any]] = {}
            for module in non_exam_items:
                fam_key = _module_course_family_key(module)
                families.setdefault(fam_key, []).append(module)

            module_selected = []
            open_choices = 0
            family_rows = []

            with st.expander(t("guided.module_components_expander", module=label), expanded=False):
                for fam_key, fam_items in sorted(families.items(), key=lambda pair: pair[0]):
                    variants: dict[str, list[Any]] = {}
                    for fam_item in fam_items:
                        variants.setdefault(_module_variant_label(fam_item), []).append(fam_item)

                    variant_names = sorted(variants.keys())
                    if len(variant_names) == 1:
                        only_variant = variant_names[0]
                        module_selected.extend(variants[only_variant])
                        family_rows.append(
                            {
                                c("course_component"): fam_key,
                                c("component_type"): t("guided.component_mandatory"),
                                c("selection"): only_variant,
                                c("variants"): ", ".join(variant_names),
                            }
                        )
                    else:
                        selector_key = f"variant_select::{key}::{fam_key}"
                        options = [t("guided.not_selected")] + variant_names
                        choice = st.selectbox(
                            t("guided.variant_select_label", family=fam_key),
                            options=options,
                            key=selector_key,
                            help=t("guided.variant_select_help"),
                        )
                        if choice != t("guided.not_selected"):
                            module_selected.extend(variants[choice])
                        else:
                            open_choices += 1

                        family_rows.append(
                            {
                                c("course_component"): fam_key,
                                c("component_type"): t("guided.component_choice"),
                                c("selection"): choice,
                                c("variants"): ", ".join(variant_names),
                            }
                        )

                if include_exams:
                    module_selected.extend(exam_items)

                if family_rows:
                    st.dataframe(pd.DataFrame(family_rows), hide_index=True, width="stretch")
                st.caption(
                    t("guided.module_caption", exams=len(exam_items), open=open_choices)
                )

            selected_by_module_key[key] = module_selected
            selected_modules.extend(module_selected)
            module_status_rows.append(
                {
                    c("module_group"): label,
                    c("open_choice_components"): open_choices,
                    c("selected_rows"): len(module_selected),
                    c("status"): t("guided.status.incomplete") if open_choices > 0 else t("guided.status.complete"),
                }
            )

        # Deduplicate selected modules by object identity.
        unique_selected = []
        seen_ids = set()
        for module in selected_modules:
            mid = id(module)
            if mid in seen_ids:
                continue
            seen_ids.add(mid)
            unique_selected.append(module)
        selected_modules = unique_selected

        # Enrich module status with conflict information.
        selected_conflicts = find_time_conflicts(selected_modules)
        conflict_module_ids = {id(left) for left, _ in selected_conflicts} | {id(right) for _, right in selected_conflicts}
        for row in module_status_rows:
            matching_key = None
            for key, items in grouped_modules.items():
                if _module_group_display(key, items) == row[c("module_group")]:
                    matching_key = key
                    break
            module_conflicts = 0
            if matching_key is not None:
                module_conflicts = sum(1 for m in selected_by_module_key.get(matching_key, []) if id(m) in conflict_module_ids)

            row[c("conflict_rows")] = module_conflicts
            if module_conflicts > 0 and row[c("status")] == t("guided.status.complete"):
                row[c("status")] = t("guided.status.complete_conflicts")
            elif module_conflicts > 0 and row[c("status")] == t("guided.status.incomplete"):
                row[c("status")] = t("guided.status.incomplete_conflicts")

        if module_status_rows:
            st.markdown(t("guided.step5"))
            st.dataframe(pd.DataFrame(module_status_rows), hide_index=True, width="stretch")

    elif selection_mode == t("guided.mode.course"):
        grouped: dict[str, list[tuple[int, Any, str, bool]]] = {}
        for module_id, module in filtered_with_ids:
            base, variant, name_exam_flag = _split_course_variant(module.modulname)
            is_exam = bool(getattr(module, "ist_pruefung", False) or name_exam_flag)
            grouped.setdefault(base, []).append((module_id, module, variant, is_exam))

        group_rows = []
        selected_bases_prev = set(st.session_state.get("selected_course_bases", []))
        for base, items in sorted(grouped.items(), key=lambda item: item[0].lower()):
            dates = sorted({it[1].datum for it in items if getattr(it[1], "datum", None) is not None})
            variants = sorted({it[2] for it in items if it[2]})
            exam_count = sum(1 for it in items if it[3])
            first_date = dates[0].strftime("%Y-%m-%d") if dates else ""
            last_date = dates[-1].strftime("%Y-%m-%d") if dates else ""
            date_range = f"{first_date} - {last_date}" if first_date and last_date else ""
            default_selected = base in selected_bases_prev

            group_rows.append(
                {
                    c("select"): default_selected,
                    c("base_course"): base,
                    c("rows"): len(items),
                    c("variants_count"): len(variants),
                    c("exam_dates"): exam_count,
                    c("period"): date_range,
                }
            )

        df_groups = pd.DataFrame(group_rows)
        edited_groups = st.data_editor(
            df_groups,
            hide_index=True,
            width="stretch",
            disabled=[c("base_course"), c("rows"), c("variants_count"), c("exam_dates"), c("period")],
            column_config={c("select"): st.column_config.CheckboxColumn(c("select"))},
            key="course_group_selector_editor",
        )

        selected_bases = set(edited_groups.loc[edited_groups[c("select")] == True, c("base_course")].tolist())
        st.session_state.selected_course_bases = sorted(selected_bases)

        selected_modules = []
        for base, items in grouped.items():
            if base not in selected_bases:
                continue
            for _, module, _, is_exam in items:
                if (not include_exams) and is_exam:
                    continue
                selected_modules.append(module)

        with st.expander(t("guided.course_details_expander")):
            for base, items in sorted(grouped.items(), key=lambda item: item[0].lower()):
                variant_labels = sorted({it[2] if it[2] else "STANDARD" for it in items})
                exam_count = sum(1 for it in items if it[3])
                st.markdown(f"**{base}**")
                st.caption(t("guided.course_details_caption", variants=", ".join(variant_labels), exams=exam_count))

    else:
        rows = []
        excluded_exam_rows = 0
        for module_id, module in filtered_with_ids:
            _, _, is_exam = _split_course_variant(module.modulname)
            if (not include_exams) and is_exam:
                excluded_exam_rows += 1
                continue
            rows.append(_module_to_row(module, module_id, selected_lookup.get(id(module), False)))

        if excluded_exam_rows:
            st.caption(t("guided.exams_hidden_caption", count=excluded_exam_rows))

        df_choice = pd.DataFrame(rows)
        edited = st.data_editor(
            df_choice,
            hide_index=True,
            width="stretch",
            disabled=[
                c("id"),
                c("module_no"),
                c("course_no"),
                c("module"),
                c("weekday"),
                c("date"),
                c("start"),
                c("end"),
                c("exam"),
                c("type"),
                c("lecturers"),
                c("ects"),
            ],
            column_config={
                c("select"): st.column_config.CheckboxColumn(c("select")),
            },
            key="course_selector_editor",
        )

        selected_ids = set(edited.loc[edited[c("select")] == True, c("id")].tolist())
        selected_modules = [m for idx, m in modules_with_id if idx in selected_ids]

    st.info(t("guided.current_selection", selected=len(selected_modules), filtered=len(filtered)))
    st.session_state.selected_modules = selected_modules
    return selected_modules


# ==========================================
# 4. MAIN UI COMPONENTS
# ==========================================
# Im Abschnitt # 4. MAIN UI COMPONENTS die render_sidebar anpassen:

def render_sidebar() -> None:
    """Renders the sidebar for data upload, global settings, and export."""
    with st.sidebar:
        st.header(t("sidebar.header"))
        st.markdown(t("sidebar.description"))

        with st.container(border=True):
            st.markdown(f"**{t('sidebar.section.data')}**")
            language_options = {
                t("sidebar.language_option.de"): "de",
                t("sidebar.language_option.en"): "en",
                t("sidebar.language_option.fr"): "fr",
            }
            selected_language = st.selectbox(
                t("sidebar.language"),
                options=list(language_options.keys()),
                index=["de", "en", "fr"].index(st.session_state.get("ui_language", "de")),
                key="sidebar_language_selector",
            )
            st.session_state.ui_language = language_options[selected_language]

            uploaded_file = st.file_uploader(
                t("sidebar.upload_label"),
                type=["csv", "xlsx", "xls"],
                help=t("sidebar.upload_help")
            )

            if uploaded_file is not None:
                # Only trigger processing if a new file is uploaded or state is empty
                if st.session_state.raw_data is None or uploaded_file.name not in str(st.session_state.raw_data):
                    with st.spinner(t("sidebar.parsing")):
                        handle_file_upload(uploaded_file)
            else:
                # Reset state if file is removed
                st.session_state.raw_data = None
                st.session_state.processed_modules = []
                st.session_state.conflicts = []
                st.session_state.selected_modules = []
                st.session_state.selected_course_bases = []

        with st.container(border=True):
            st.markdown(f"**{t('sidebar.section.settings')}**")
            target_ects = st.number_input(t("sidebar.target_ects"), min_value=0, max_value=60, value=30, step=1)
            st.session_state.target_ects = target_ects

        if st.session_state.processed_modules:
            st.divider()
            modules_for_export = st.session_state.get("selected_modules") or st.session_state.processed_modules
            render_export_section(modules_for_export)


def render_dashboard(modules: List, target_ects: int, all_modules: List[Any]) -> None:
    """Render dashboard with key stats and analysis visuals."""
    st.subheader(t("dashboard.subheader"))

    if not modules:
        st.info(t("dashboard.no_modules"))
        return

    st.caption(t("dashboard.caption"))

    total_ects = sum(m.ects for m in modules)
    total_modules = len(modules)
    unique_days = len(set(_weekday_label(m) for m in modules))
    total_pruefungen = sum(1 for m in modules if getattr(m, "ist_pruefung", False))
    conflict_pairs = find_time_conflicts(modules)
    selected_base_count = len({_module_group_title(m) for m in modules})
    lessons_per_week, hours_per_week, observed_weeks = _lessons_per_week(modules)
    absence_settings = _absence_settings()
    absence_rules = _absence_rules_summary(absence_settings)
    absence_selected_df = _absence_conflict_dataframe(modules, absence_settings)
    absence_all_df = _absence_conflict_dataframe(all_modules, absence_settings)
    absence_course_df = _absence_course_impact_dataframe(modules, absence_settings)

    with st.container(border=True):
        st.markdown(f"**{t('dashboard.section.metrics')}**")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(t("dashboard.metric.ects"), total_ects, delta=total_ects - target_ects)
        with col2:
            st.metric(t("dashboard.metric.rows"), total_modules)
        with col3:
            st.metric(t("dashboard.metric.base_courses"), selected_base_count)
        with col4:
            st.metric(t("dashboard.metric.exams"), total_pruefungen)

        col5, col6 = st.columns(2)
        with col5:
            st.metric(t("dashboard.metric.weekdays"), unique_days)
        with col6:
            st.metric(t("dashboard.metric.lessons"), lessons_per_week)
            st.caption(t("dashboard.metric.lessons_caption", hours=hours_per_week, weeks=observed_weeks))

        col7, col8 = st.columns(2)
        with col7:
            st.metric(t("dashboard.metric.absence_rules"), len(absence_rules))
        with col8:
            st.metric(t("dashboard.metric.absence_rows"), len(absence_selected_df))

    with st.container(border=True):
        st.markdown(f"**{t('dashboard.section.absence')}**")
        if not absence_rules:
            st.info(t("dashboard.absence.none"))
        else:
            st.caption(t("dashboard.absence.active"))
            for rule in absence_rules:
                st.markdown(f"- {rule}")

            st.markdown(t("dashboard.absence.current_selection"))
            if absence_selected_df.empty:
                st.success(t("dashboard.absence.current_selection_none"))
            else:
                st.warning(t("dashboard.absence.current_selection_conflicts", count=len(absence_selected_df)))
                st.dataframe(_style_absence_rows(absence_selected_df, c("reason")), hide_index=True, width="stretch")

            st.markdown(t("dashboard.absence.course_impact_title"))
            if absence_course_df.empty:
                st.info(t("dashboard.absence.course_impact_none"))
            else:
                st.caption(t("dashboard.absence.course_impact_caption"))
                st.dataframe(_style_risk_rows(absence_course_df), hide_index=True, width="stretch")

            st.markdown(t("dashboard.absence.all_data"))
            if absence_all_df.empty:
                st.info(t("dashboard.absence.all_data_none"))
            else:
                st.caption(t("dashboard.absence.all_data_caption", count=len(absence_all_df)))
                st.dataframe(absence_all_df.head(50), hide_index=True, width="stretch")

    overlap_summary = _calculate_module_overlap_summary(modules)
    exam_df = _calculate_exam_feasibility(modules)
    semester_timeline = _semester_timeline_figure(modules)
    daily_load = _daily_load_figure(modules)

    with st.container(border=True):
        st.markdown(f"**{t('dashboard.section.visuals')}**")
        chart_col1, chart_col2 = st.columns([1.2, 1])
        with chart_col1:
            st.markdown(t("dashboard.chart.weekday_title"))
            st.caption(t("dashboard.chart.weekday_caption"))
            fig = _weekday_bar_figure(modules)
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True)
        with chart_col2:
            st.markdown(t("dashboard.chart.overlap_title"))
            st.caption(t("dashboard.chart.overlap_caption"))
            fig = _overlap_bar_figure(overlap_summary)
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True)

        if semester_timeline is not None:
            st.markdown(t("dashboard.section.semester_timeline"))
            st.caption(t("dashboard.chart.semester_caption"))
            st.plotly_chart(semester_timeline, use_container_width=True)

        if daily_load is not None:
            st.markdown(t("dashboard.section.daily_load"))
            st.caption(t("dashboard.chart.daily_load_caption"))
            st.plotly_chart(daily_load, use_container_width=True)

    with st.container(border=True):
        st.markdown(t("dashboard.section.kpis"))
        summary_table = pd.DataFrame(
            [
                {c("metric"): t("dashboard.kpi.conflict_pairs"), c("value"): len(conflict_pairs)},
                {c("metric"): t("dashboard.kpi.modules_overlap"), c("value"): int((overlap_summary[c("overlap_total_min")] > 0).sum()) if not overlap_summary.empty else 0},
                {c("metric"): t("dashboard.kpi.avg_overlap"), c("value"): round(overlap_summary[c("overlap_total_min")].mean(), 1) if not overlap_summary.empty else 0},
            ]
        )
        st.dataframe(summary_table, hide_index=True, width="stretch")

        if not exam_df.empty:
            st.markdown(t("dashboard.section.exam_status"))
            st.dataframe(exam_df, hide_index=True, width="stretch")

        if not overlap_summary.empty:
            st.markdown(t("dashboard.section.overlap_rate"))
            st.dataframe(overlap_summary, hide_index=True, width="stretch")

def render_timetable(modules: List) -> None:
    """Render a visual weekly schedule with timeline and daily breakdown."""
    st.subheader(t("timetable.subheader"))

    if not modules:
        st.warning(t("timetable.no_modules"))
        return

    with st.container(border=True):
        st.caption(t("timetable.caption"))
        fig = _weekly_timeline_figure(modules)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)

    with st.container(border=True):
        st.markdown(f"**{t('timetable.section.daily_details')}**")
        settings = _absence_settings()
        blocked_days = settings.get("blocked_days", set()) if settings.get("blocked_enabled") else set()
        day_order = _weekday_labels_in_order()
        for day in day_order:
            daily_mods = sorted([m for m in modules if _weekday_label(m) == day], key=lambda x: x.startzeit)
            day_key = _weekday_keys_in_order()[day_order.index(day)]
            day_blocked = day_key in blocked_days
            if not daily_mods and not day_blocked:
                continue

            with st.expander(t("timetable.day_expander", day=day, count=len(daily_mods)), expanded=day_blocked):
                if day_blocked:
                    st.error(t("timetable.blocked_day_warning", halfday=settings.get("blocked_halfday", t("guided.full_day"))))

                for mod in daily_mods:
                    exam_tag = f" | {t('timetable.exam_tag')}" if getattr(mod, "ist_pruefung", False) else ""
                    reasons = _absence_reasons_for_module(mod, settings)
                    prefix = "🔴 " if reasons else ""
                    st.markdown(
                        f"{prefix}**{mod.startzeit.strftime('%H:%M')} - {mod.endzeit.strftime('%H:%M')}**"
                        f" | {mod.modulname}{exam_tag}"
                    )
                    st.caption(
                        t(
                            "timetable.entry_caption",
                            module_no=getattr(mod, "modul_nr", None) or t("common.na"),
                            course_no=getattr(mod, "kurs_nr", None) or t("common.na"),
                            mod_type=mod.modultyp,
                            room=mod.raum,
                        )
                    )
                    if reasons:
                        st.caption(t("timetable.absence_reason", reason=", ".join(reasons)))

def render_conflict_analysis(conflicts: List[Tuple], selected_modules: List[Any], all_modules: List[Any]) -> None:
    """Render detailed conflict tables and feasibility analysis."""
    st.subheader(t("conflicts.subheader"))

    absence_settings = _absence_settings()
    absence_selected_df = _absence_conflict_dataframe(selected_modules, absence_settings)
    absence_all_df = _absence_conflict_dataframe(all_modules, absence_settings)
    absence_course_df = _absence_course_impact_dataframe(selected_modules, absence_settings)

    if not selected_modules and not conflicts and absence_all_df.empty:
        st.info(t("conflicts.empty_hint"))
        return

    if conflicts:
        st.error(t("conflicts.found", count=len(conflicts)))
    else:
        if absence_selected_df.empty:
            st.success(t("conflicts.none"))
        else:
            st.warning(t("conflicts.none_time_but_absence"))

    if conflicts:
        conflict_summary_df = _summarize_conflicts(conflicts)
        conflict_rows = []
        for left, right in conflicts:
            overlap = _minutes_overlap(left, right)
            left_duration = max(1, left.duration_minutes)
            right_duration = max(1, right.duration_minutes)
            conflict_rows.append(
                {
                    c("date"): _conflict_date_label(left),
                    c("weekday"): _weekday_label(left),
                    c("module_1"): _module_label(left),
                    c("module_2"): _module_label(right),
                    c("time_1"): f"{left.startzeit.strftime('%H:%M')} - {left.endzeit.strftime('%H:%M')}",
                    c("time_2"): f"{right.startzeit.strftime('%H:%M')} - {right.endzeit.strftime('%H:%M')}",
                    c("overlap_min"): overlap,
                    c("overlap_pct_module_1"): round((overlap / left_duration) * 100, 1),
                    c("overlap_pct_module_2"): round((overlap / right_duration) * 100, 1),
                }
            )

        conflict_df = pd.DataFrame(conflict_rows).sort_values([c("date"), c("overlap_min"), c("weekday")], ascending=[True, False, True])

        with st.container(border=True):
            if not conflict_summary_df.empty:
                st.markdown(t("conflicts.summary_title"))
                st.dataframe(conflict_summary_df, hide_index=True, width="stretch")

            if not conflict_df.empty:
                top_conflicts = conflict_df.head(8).copy()
                fig = px.bar(
                    top_conflicts,
                    x=c("overlap_min"),
                    y=c("module_1"),
                    color=c("module_2"),
                    orientation="h",
                    title=t("chart.conflict_top"),
                )
                fig.update_layout(height=max(420, 44 * len(top_conflicts) + 120), margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(fig, use_container_width=True)

                by_day = conflict_df.groupby(c("weekday"), as_index=False)[c("overlap_min")].sum()
                fig_day = px.pie(by_day, values=c("overlap_min"), names=c("weekday"), title=t("conflicts.chart.by_weekday"))
                fig_day.update_layout(height=360, margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(fig_day, use_container_width=True)

                by_date = conflict_df.groupby(c("date"), as_index=False)[c("overlap_min")].sum()
                fig_date = px.bar(by_date, x=c("date"), y=c("overlap_min"), title=t("conflicts.chart.by_date"))
                fig_date.update_layout(height=340, margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(fig_date, use_container_width=True)

        with st.container(border=True):
            st.markdown(t("conflicts.details_title"))
            st.dataframe(conflict_df.style.background_gradient(subset=[c("overlap_min")], cmap="Reds"), hide_index=True, width="stretch")
            st.markdown(t("conflicts.interpretation_title"))
            st.caption(t("conflicts.interpretation_text"))

    with st.container(border=True):
        st.markdown(t("conflicts.absence_title"))
        if absence_all_df.empty:
            st.info(t("conflicts.absence_none"))
        else:
            if absence_selected_df.empty:
                st.success(t("conflicts.absence_selected_none"))
            else:
                st.warning(t("conflicts.absence_selected_found", count=len(absence_selected_df)))
                st.dataframe(_style_absence_rows(absence_selected_df, c("reason")), hide_index=True, width="stretch")

            st.markdown(t("conflicts.absence_course_title"))
            if absence_course_df.empty:
                st.info(t("conflicts.absence_course_none"))
            else:
                st.dataframe(_style_risk_rows(absence_course_df), hide_index=True, width="stretch")

            st.caption(t("conflicts.absence_all_caption", count=len(absence_all_df)))
            st.dataframe(_style_absence_rows(absence_all_df.head(80), c("reason")), hide_index=True, width="stretch")

def render_raw_data() -> None:
    """Displays source data and a cleaned, student-friendly raw view."""
    st.subheader(t("raw.subheader"))
    if st.session_state.raw_data is None:
        st.info(t("raw.no_data"))
        return

    raw_df = st.session_state.raw_data.copy()
    raw_df.columns = [str(col) for col in raw_df.columns]
    for col in raw_df.columns:
        if raw_df[col].dtype == "object":
            raw_df[col] = raw_df[col].astype(str)

    col1, col2 = st.columns([1.1, 0.9])
    with col1:
        with st.container(border=True):
            st.markdown(t("raw.original"))
            st.dataframe(raw_df, width="stretch", hide_index=True)

    with col2:
        with st.container(border=True):
            st.markdown(t("raw.help_title"))
            st.write(t("raw.help_text"))

        if st.session_state.get("selected_modules"):
            with st.container(border=True):
                st.markdown(t("raw.selected"))
                sel_df = pd.DataFrame([_module_to_ui_row(m) for m in st.session_state.selected_modules])
                st.dataframe(sel_df, width="stretch", hide_index=True)

# ==========================================
# 5. MAIN APPLICATION CONTROLLER
# ==========================================
def main() -> None:
    """Main application loop."""
    # Ensure backend modules are loaded before rendering the app
    if not MODULES_AVAILABLE:
        st.stop()

    # Render Sidebar
    render_sidebar()

    st.title(t("app.title"))
    st.markdown(t("app.subtitle"))

    with st.container(border=True):
        st.markdown(f"**{t('app.quickstart_title')}**")
        st.caption(t("app.quickstart_text"))

    selected_modules = st.session_state.processed_modules

    # Create UI Tabs for a cleaner application state
    tab_guided, tab_dashboard, tab_timetable, tab_conflicts, tab_data = st.tabs([
        t("app.tab.guided"),
        t("app.tab.dashboard"), 
        t("app.tab.timetable"), 
        t("app.tab.conflicts"), 
        t("app.tab.raw")
    ])

    with tab_guided:
        selected_modules = render_guided_planning(st.session_state.processed_modules)
    
    # Render Content in Tabs
    with tab_dashboard:
        render_dashboard(selected_modules, st.session_state.get('target_ects', 30), st.session_state.processed_modules)
        
    with tab_timetable:
        if selected_modules:
            render_timetable(selected_modules)
        else:
            st.info(t("app.info.no_selection_guided"))
            
    with tab_conflicts:
        if selected_modules:
            selected_conflicts = find_time_conflicts(selected_modules)
            render_conflict_analysis(selected_conflicts, selected_modules, st.session_state.processed_modules)
        else:
            render_conflict_analysis([], selected_modules, st.session_state.processed_modules)
            
    with tab_data:
        render_raw_data()

# ==========================================
# ENTRY POINT
# ==========================================
if __name__ == "__main__":
    main()