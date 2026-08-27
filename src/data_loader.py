"""
ZHAW MSc Psychology - Timetable Planner (Data Integration Layer)
Author: HealthData CodeArchitect
Description: Robust data ingestion, validation, and transformation module.
Focuses on defensive programming to ensure high UI/UX stability by catching
and correcting data anomalies before they reach the presentation layer.

Pipeline overview (see `load_schedule_from_dataframe` for the entry point):
    raw DataFrame (from st.file_uploader via pandas)
        -> _try_reheader_from_rows   find & promote the real header row,
                                      skipping title/note banner rows that
                                      real ZHAW exports place above it
        -> _normalize_columns        map many header spellings (German/
                                      English, with/without umlauts) onto
                                      one canonical internal schema
        -> _sanitize_dataframe       coerce types, parse dates/times/%,
                                      drop obviously-junk rows
        -> ZHAWModule(**row)         final strict validation (models.py),
                                      one row at a time so a single bad
                                      row doesn't sink the whole import

This tolerance is deliberate: real university timetable exports are messy
(merged header cells, metadata banners, inconsistent date formats, stray
whitespace) and a student uploading their own file should get as much of
their schedule imported as possible rather than a hard failure on the
first oddity - errors here should degrade gracefully to "skip this row,
warn about it" rather than "reject the whole file".
"""

import pandas as pd
import logging
import re
from datetime import date, datetime
from typing import List, Dict, Any
from pydantic import ValidationError

# Assuming ZHAWModule is a Pydantic BaseModel defined in models.py
from models import ZHAWModule

# ==========================================
# 1. LOGGING CONFIGURATION
# ==========================================
# Set up a module-specific logger for backend debugging without cluttering the UI
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# ==========================================
# 2. CUSTOM EXCEPTIONS
# ==========================================
class DataLoaderError(Exception):
    """
    Base exception for data loading issues. Designed to be caught by the GUI.

    `i18n_key`/`i18n_kwargs` let app.py show this message translated via
    t(i18n_key, **i18n_kwargs) instead of the English `message` passed here
    - without them, a German/French user would see this raw English text
    wrapped inside an otherwise-translated sentence. `message` is still
    always set (used for server-side logging and as the str(exc) fallback).
    """
    def __init__(self, message: str, i18n_key: str | None = None, **i18n_kwargs):
        super().__init__(message)
        self.i18n_key = i18n_key
        self.i18n_kwargs = i18n_kwargs

class MissingColumnError(DataLoaderError):
    """Raised when critical columns are missing from the uploaded dataset."""
    pass

class DataSanitizationError(DataLoaderError):
    """Raised when the data cannot be coerced into the required formats."""
    pass

# ==========================================
# 3. CONSTANTS & MAPPINGS
# ==========================================
# Define the critical columns required for the application to function.
# This serves as our schema contract.
REQUIRED_COLUMNS = {
    "wochentag", 
    "startzeit", 
    "endzeit", 
    "modulname", 
    "ects"
}

# Minimal columns needed to detect a timetable header row in raw exports.
HEADER_REQUIRED_COLUMNS = {
    "wochentag",
    "startzeit",
    "endzeit",
}

# Optional columns that enhance the UI but aren't strictly necessary for the algorithm
OPTIONAL_COLUMNS = {
    "modultyp", 
    "dozierende", 
    "raum",
    "datum",
    "modul_nr",
    "kurs_nr",
    "pruefung_flag",
    "ist_pruefung",
    "anwesenheitspflicht_prozent",
}

# Map common upload header variants to the canonical internal schema.
COLUMN_ALIASES = {
    "modulname": {
        "modul", "module", "modul_name", "course", "course_name", "kurs", "veranstaltung", "titel",
        "lehrveranstaltung", "veranstaltungsname", "fach", "fachname", "bezeichnung", "modulbezeichnung",
        "anlassbezeichnung", "anlass", "module_title", "modultitel"
    },
    "wochentag": {
        "tag", "weekday", "day", "wochentag_name", "wochentag/datum", "wochentag_datum"
    },
    "startzeit": {
        "start", "startzeitpunkt", "start_time", "beginn", "beginnzeit", "von", "uhrzeit_von",
        "zeit_von", "startzeit/von"
    },
    "endzeit": {
        "ende", "end", "endzeitpunkt", "end_time", "schluss", "bis", "uhrzeit_bis", "zeit_bis", "endzeit/bis"
    },
    "ects": {
        "credit", "credits", "credit_points", "kreditpunkte", "kp", "ects_punkte", "ects-credits",
        "ects_credits", "credit_points_ects"
    },
    "modultyp": {
        "typ", "veranstaltungsart", "art", "modulart", "modul_typ"
    },
    "dozierende": {
        "dozent", "dozentin", "dozierender", "lecturer", "teacher", "instructor", "lehrperson", "lehrpersonen"
    },
    "raum": {
        "room", "ort", "location", "zimmer"
    },
    "datum": {
        "datum", "date", "veranstaltungsdatum", "kalenderdatum"
    },
    "modul_nr": {
        "modul_nr", "modul_n", "modulnr", "moduli", "modul_i", "modul-id", "modul_id"
    },
    "kurs_nr": {
        "kurs_nr", "kurs_n", "kursnr", "kurs_n", "kurs-id", "kurs_id"
    },
    "pruefung_flag": {
        "pruefung", "prüfung", "pruef", "pruefu", "pruefungsflag", "exam", "assessment"
    },
    "ist_pruefung": {
        "ist_pruefung", "is_exam", "exam_flag"
    },
    "anwesenheitspflicht_prozent": {
        "anwesenheit", "anwesenheitspflicht", "anwesenheitspflicht_prozent", "anwesenheitspflicht_%",
        "praesenz", "praesenzpflicht", "attendance", "attendance_requirement", "attendance_required",
        "presence", "presence_requirement", "mandatory_attendance"
    },
}


def _normalize_label(value: Any) -> str:
    """Normalize any header-like value to the canonical comparison format."""
    if value is None:
        return ""
    label = str(value).strip().lower().replace("\n", " ")
    label = (
        label.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    # Keep separators as underscores but strip other punctuation/noise.
    label = re.sub(r"[^a-z0-9/ _:-]", "", label)
    label = label.replace(":", " ").replace("-", "_").replace("/", "_")
    return "_".join(label.split())


def _canonicalize_header_labels(labels: List[Any]) -> List[str]:
    """Map raw labels to normalized canonical/alias column names."""
    result: List[str] = []
    for raw in labels:
        label = _normalize_label(raw)
        mapped = label
        for canonical, aliases in COLUMN_ALIASES.items():
            if label == canonical or label in aliases:
                mapped = canonical
                break
        result.append(mapped)
    return result


def _try_reheader_from_rows(df: pd.DataFrame, max_scan_rows: int = 20) -> pd.DataFrame:
    """
    Detect and promote a row to header when spreadsheet exports contain metadata lines.

    Real ZHAW exports are read with `header=None` (see app.py's Excel
    branch) so this function always sees the *raw* grid, including things
    like a title banner ("Vorlesungsverzeichnis Master HS 2026 ...") and a
    yellow note row above the real column header. This function scans the
    first `max_scan_rows` rows looking for the row that best matches our
    expected column names, and promotes it to be the DataFrame header,
    discarding everything above it.

    Two scoring passes run per row index:
      - "required hits": how many of the 3 columns we absolutely need to
        even recognize a timetable (wochentag/startzeit/endzeit) this row
        contains, when normalized/alias-mapped.
      - "total hits": same but across the full required+optional schema,
        used as a tiebreaker once required hits are equal.
    The moment a row hits ALL required columns and >=3 total columns, it's
    accepted immediately as a confident match. If no row is ever that
    confident (e.g. an export with unusual headers), the single
    best-scoring row seen across the whole scan is used instead as a
    lenient fallback, as long as it clears a low minimum bar.
    """
    if df.empty:
        return df

    scan_limit = min(max_scan_rows, len(df))
    best_headers: List[str] | None = None
    best_start_row = 0
    best_required_hits = -1
    best_total_hits = -1

    def evaluate_headers(raw_headers: List[Any]) -> List[str]:
        return _canonicalize_header_labels(raw_headers)

    for idx in range(scan_limit):
        row_values = df.iloc[idx].tolist()
        candidates: List[tuple[List[str], int]] = []

        # Candidate 1: this row alone is the header.
        candidates.append((evaluate_headers(row_values), idx + 1))

        # Candidate 2: two-line header (common in exports with merged cells,
        # e.g. "Kurs" on one line and "Nr." directly below it forming
        # "Kurs Nr." together) - concatenate row idx and idx+1 cell-by-cell
        # and treat the combination as one more header candidate.
        if idx + 1 < scan_limit:
            next_values = df.iloc[idx + 1].tolist()
            combined_values = []
            for left, right in zip(row_values, next_values):
                left_norm = _normalize_label(left)
                right_norm = _normalize_label(right)
                combined = " ".join([part for part in [left_norm, right_norm] if part]).strip()
                combined_values.append(combined)
            candidates.append((evaluate_headers(combined_values), idx + 2))

        for candidate_headers, data_start_row in candidates:
            candidate_set = set(candidate_headers)
            required_hits = len(HEADER_REQUIRED_COLUMNS & candidate_set)
            total_hits = len((REQUIRED_COLUMNS | OPTIONAL_COLUMNS) & candidate_set)

            # Track the best candidate seen so far, in case no row ever
            # reaches the "confident match" bar below and we must fall
            # back to the least-bad guess.
            if (
                required_hits > best_required_hits
                or (required_hits == best_required_hits and total_hits > best_total_hits)
            ):
                best_headers = candidate_headers
                best_start_row = data_start_row
                best_required_hits = required_hits
                best_total_hits = total_hits

            # Confident match: all 3 required columns present, plus enough
            # optional columns to be sure this is a real header and not a
            # data row that coincidentally contains e.g. the word "Montag".
            is_header_candidate = HEADER_REQUIRED_COLUMNS.issubset(candidate_set) and total_hits >= 3
            if is_header_candidate:
                logger.info(f"Detected header row at index {idx}. Rebuilding dataframe header.")
                rebuilt = df.iloc[data_start_row:].copy().reset_index(drop=True)
                rebuilt.columns = candidate_headers
                rebuilt = rebuilt.loc[:, ~pd.Series(rebuilt.columns).duplicated().to_numpy()]
                return rebuilt

    # Fallback: use best partial match if it has enough structure to proceed.
    if best_headers is not None and best_required_hits >= 2 and best_total_hits >= 3:
        logger.info(
            f"Using best partial header match (required hits: {best_required_hits}, total hits: {best_total_hits})."
        )
        rebuilt = df.iloc[best_start_row:].copy().reset_index(drop=True)
        rebuilt.columns = best_headers
        rebuilt = rebuilt.loc[:, ~pd.Series(rebuilt.columns).duplicated().to_numpy()]
        return rebuilt

    return df

# ==========================================
# 4. HELPER FUNCTIONS (DATA TRANSFORMATIONS)
# ==========================================
def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sanitizes DataFrame columns to prevent KeyError caused by minor typos,
    varying capitalizations, or trailing whitespaces in user uploads.
    
    Args:
        df (pd.DataFrame): The raw uploaded pandas DataFrame.
        
    Returns:
        pd.DataFrame: DataFrame with normalized column names.
    """
    logger.info("Normalizing dataframe column names...")
    # Coerce to plain strings first (Excel headers can be datetime/int mixed types)
    df.columns = [_normalize_label(col) for col in df.columns]

    # Drop empty/placeholder columns produced by spreadsheet exports.
    drop_cols = [c for c in df.columns if c.startswith("unnamed") or c == "nan" or c == ""]
    if drop_cols:
        df = df.drop(columns=drop_cols, errors="ignore")

    # Apply aliases to map external headers to our canonical schema keys.
    rename_map: Dict[str, str] = {}
    for col, canonical in zip(df.columns, _canonicalize_header_labels(list(df.columns))):
        if canonical != col:
            rename_map[col] = canonical

    # Avoid duplicate canonical columns after renaming by keeping the first non-empty source.
    if rename_map:
        df = df.rename(columns=rename_map)
        df = df.loc[:, ~df.columns.duplicated()]

    return df

def _parse_datum_cell(value: Any) -> Any:
    """
    Parse a single 'datum' cell robustly, preserving native Excel date
    values instead of round-tripping them through str() (which is lossy
    and can make otherwise-valid dates unparseable). Falls back to
    interpreting a bare number as a raw Excel date serial, which can leak
    through when a date column loses its cell formatting during import.
    """
    if value is None:
        return pd.NaT
    if isinstance(value, float) and pd.isna(value):
        return pd.NaT
    if isinstance(value, pd.Timestamp):
        return value
    if isinstance(value, (datetime, date)):
        return pd.Timestamp(value)

    text = str(value).strip().replace("\xa0", " ")  # \xa0 = non-breaking space, common in Excel exports
    if text.lower() in {"", "n/a", "na", "none", "nan", "nat"}:
        return pd.NaT

    # ISO-like strings ("2026-09-16" or "2026-09-16 00:00:00") are parsed
    # without `dayfirst`, since "YYYY-MM-DD" is unambiguous either way and
    # forcing dayfirst on an already-ISO string can misparse edge cases.
    if re.match(r"^\d{4}-\d{2}-\d{2}(?:[ T].*)?$", text):
        return pd.to_datetime(text, errors="coerce")

    # Everything else is assumed day-first (Swiss/German convention:
    # "16.09.2026" or "16/09/2026" means 16 September, not 9 January).
    parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    if pd.isna(parsed) and re.match(r"^\d{4,6}(\.0+)?$", text):
        # Neither ISO nor day-first parsing worked, but the value still
        # looks like a bare number (e.g. "46007" or "46007.0"). This
        # happens when a date-formatted Excel cell loses its number format
        # during import and pandas hands us the raw serial number instead
        # of a real date. Excel's day-0 is 1899-12-30 (not 1900-01-01) to
        # compensate for Excel's historical "1900 is a leap year" bug, so
        # that offset - not the epoch you'd naively expect - is required
        # for the arithmetic below to land on the correct calendar date.
        try:
            parsed = pd.Timestamp("1899-12-30") + pd.to_timedelta(float(text), unit="D")
        except (ValueError, OverflowError):
            parsed = pd.NaT
    return parsed


def _sanitize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans and prepares data types before Pydantic validation.
    Handles NaN values which frequently crash strict type validators.
    
    Args:
        df (pd.DataFrame): The normalized pandas DataFrame.
        
    Returns:
        pd.DataFrame: Sanitized DataFrame ready for object mapping.
    """
    logger.info("Sanitizing data types and handling missing values...")
    
    try:
        # Fill missing string columns with empty strings or default placeholders
        string_cols = [
            "modulname",
            "wochentag",
            "modultyp",
            "dozierende",
            "raum",
            "modul_nr",
            "kurs_nr",
            "pruefung_flag",
        ]
        for col in string_cols:
            if col in df.columns:
                df[col] = df[col].fillna("N/A").astype(str)
                df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)

        # Ensure ECTS is numeric, coercion forces invalid parsing to NaN, then fill with 0
        if "ects" in df.columns:
            df["ects"] = pd.to_numeric(df["ects"], errors="coerce").fillna(0).astype(int)

        # Standardize time strings (ensures format like "HH:MM")
        # Removing any random whitespace that might break datetime parsing
        time_cols = ["startzeit", "endzeit"]
        for col in time_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        if "datum" in df.columns:
            # Parse cell-by-cell first (see _parse_datum_cell for why: it
            # needs to see each cell's original type, e.g. a real datetime
            # vs. a plain string, before anything gets coerced). The second
            # pass just normalizes the resulting mixed Timestamp/NaT column
            # down to plain `datetime.date` (or None), which is what
            # `ZHAWModule.datum` expects.
            df["datum"] = df["datum"].apply(_parse_datum_cell)
            df["datum"] = pd.to_datetime(df["datum"], errors="coerce").dt.date

        if "anwesenheitspflicht_prozent" in df.columns:
            raw = df["anwesenheitspflicht_prozent"].astype(str).str.strip().str.replace(",", ".", regex=False)
            raw = raw.str.replace("%", "", regex=False)
            numeric = pd.to_numeric(raw, errors="coerce")
            numeric = numeric.where((numeric < 0) | (numeric > 1), numeric * 100)
            df["anwesenheitspflicht_prozent"] = numeric

        # Drop obvious non-data rows (blank lines, repeated header labels, metadata rows).
        required_like = [c for c in ["modulname", "wochentag", "startzeit", "endzeit"] if c in df.columns]
        if required_like:
            def _is_missing_like(value: Any) -> bool:
                norm = _normalize_label(value)
                return norm in {"", "n_a", "na", "none", "nan"}

            keep_mask = []
            for _, row in df.iterrows():
                # Remove rows where all required-like fields are empty placeholders.
                values = [row.get(col) for col in required_like]
                if all(_is_missing_like(v) for v in values):
                    keep_mask.append(False)
                    continue

                # Rows without both start/end times are not schedulable calendar entries.
                if "startzeit" in df.columns and "endzeit" in df.columns:
                    if _is_missing_like(row.get("startzeit")) or _is_missing_like(row.get("endzeit")):
                        keep_mask.append(False)
                        continue

                # Remove rows that look like duplicated header rows inside the sheet
                # (some exports repeat the header every time a new section/lecturer
                # group starts, which would otherwise show up as one bogus module
                # literally named "Modulname").
                row_header_tokens = {_normalize_label(row.get(col)) for col in required_like}
                if {"modulname", "wochentag", "startzeit", "endzeit"}.issubset(row_header_tokens):
                    keep_mask.append(False)
                    continue

                keep_mask.append(True)

            df = df.loc[keep_mask].reset_index(drop=True)

        return df

    except Exception as e:
        logger.error(f"Sanitization failed: {str(e)}")
        raise DataSanitizationError(
            f"Failed to clean dataset: {str(e)}",
            i18n_key="upload.error_sanitization",
            error=str(e),
        )

# ==========================================
# 5. MAIN DATA LOADER LOGIC
# ==========================================
def load_schedule_from_dataframe(raw_df: pd.DataFrame, ist_zusatzmodul: bool = False) -> List[ZHAWModule]:
    """
    Main entry point for data ingestion. Takes a raw Pandas DataFrame (uploaded via UI),
    validates its structure, sanitizes the contents, and maps it to strongly-typed
    Pydantic models (ZHAWModule).

    Args:
        raw_df (pd.DataFrame): The raw dataframe from st.file_uploader.
        ist_zusatzmodul (bool): Tags every row produced by this call as
            belonging to a supplementary-module upload (e.g. a Passerelle
            student's second, Bachelor-level module list) rather than the
            main schedule. This is set by the *caller* based on which
            upload slot the file came from - never read from the file's own
            content - see ZHAWModule.ist_zusatzmodul and
            docs/planung/KONZEPT-passerelle-zusatzmodule.md section 3 for
            why: trusting a source column here would make an app-level
            business rule dependent on the source file reliably filling
            that column, which the rest of this module's defensive
            sanitizing philosophy deliberately avoids.

    Returns:
        List[ZHAWModule]: A list of validated module objects.

    Raises:
        MissingColumnError: If essential scheduling columns are absent.
        DataLoaderError: For general Pydantic validation failures.
    """
    if raw_df is None or raw_df.empty:
        logger.warning("Received empty DataFrame.")
        return []

    # 1. Create an isolated copy to prevent SettingWithCopyWarnings
    df = raw_df.copy()

    # 2. Try recovering real header row from metadata-heavy spreadsheet exports.
    df = _try_reheader_from_rows(df, max_scan_rows=80)

    # 3. Normalize columns (e.g., " Startzeit " -> "startzeit")
    df = _normalize_columns(df)

    # Fill required semantic fields from common alternatives when possible.
    if "modulname" not in df.columns:
        for fallback_col in ["anlassbezeichnung", "modul", "kurs_nr", "modulart"]:
            if fallback_col in df.columns:
                logger.info(f"Using '{fallback_col}' as fallback source for modulname.")
                df["modulname"] = df[fallback_col]
                break

    # Some source exports (e.g. the ZHAW Bachelor-level course catalog used
    # by Passerelle students, see docs/planung/KONZEPT-passerelle-zusatzmodule.md
    # section 2.2) carry a date column but no separate weekday column at
    # all - unlike the Master catalog's "Tag" column, there's no alias to
    # match. Rather than rejecting the whole file over one derivable field,
    # derive `wochentag` from `datum` here (before it's actually needed for
    # anything downstream). This is a general robustness improvement, not
    # specific to any one source format - it helps any upload missing a
    # weekday column as long as it has dates.
    if "wochentag" not in df.columns and "datum" in df.columns:
        logger.info("No weekday column found. Deriving 'wochentag' from 'datum'.")
        weekday_names = ["montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag"]
        parsed_dates = pd.to_datetime(df["datum"].apply(_parse_datum_cell), errors="coerce")
        df["wochentag"] = parsed_dates.dt.weekday.apply(
            lambda w: weekday_names[int(w)] if pd.notna(w) else None
        )

    # 4. Structural Validation
    current_cols = set(df.columns)
    missing_cols = REQUIRED_COLUMNS - current_cols
    # If only ECTS is absent, keep processing and default it to 0.
    if missing_cols == {"ects"}:
        logger.info("ECTS column not found. Defaulting ECTS to 0.")
        df["ects"] = 0
        missing_cols = set()

    if missing_cols:
        detected_cols = ", ".join(list(df.columns)[:20])
        error_msg = (
            f"Invalid dataset format. Missing critical columns: {', '.join(sorted(missing_cols))}. "
            f"Detected columns: {detected_cols}"
        )
        logger.error(error_msg)
        # Raising a custom error allows the GUI to catch it and display a friendly st.error()
        raise MissingColumnError(
            error_msg,
            i18n_key="upload.error_missing_columns",
            missing=", ".join(sorted(missing_cols)),
            detected=detected_cols,
        )

    # 5. Data Sanitization (Handle NaNs, cast types securely)
    df = _sanitize_dataframe(df)

    # Tag every row with its origin *after* sanitization (so this can't be
    # dropped/overwritten by anything above) and as a plain column (so both
    # the normal and the datum-retry row_dict below - see step 6 - pick it
    # up automatically via row.to_dict(), without needing a second call
    # site to remember to set it).
    df["ist_zusatzmodul"] = bool(ist_zusatzmodul)

    # 6. Object Mapping (DataFrame -> List[Pydantic Models])
    processed_modules: List[ZHAWModule] = []
    validation_errors = 0
    suppressed_validation_logs = 0
    validation_log_limit = 20

    logger.info(f"Attempting to parse {len(df)} rows into ZHAWModule objects.")
    
    for index, row in df.iterrows():
        try:
            # Convert pandas Series to dictionary, filtering out unexpected columns dynamically
            row_dict: Dict[str, Any] = row.to_dict()
            
            # Instantiate Pydantic model (which handles internal datetime parsing and strict validation)
            module_obj = ZHAWModule(**row_dict)
            processed_modules.append(module_obj)
            
        except ValidationError as ve:
            # Graceful degradation: if `datum` is the *only* field that
            # failed validation (e.g. a genuinely garbled date string that
            # slipped past _parse_datum_cell), don't discard the whole row
            # over one bad field - retry once with datum forced to None.
            # The row still carries useful info (module name, time, room,
            # ...) and the app surfaces a "N rows without a date" warning
            # to the user (see app.py's _warn_if_dates_missing) so this
            # degradation is visible rather than silent data loss.
            errors = ve.errors()
            locations = {err.get("loc", [None])[0] for err in errors if err.get("loc")}
            if locations == {"datum"}:
                row_dict = row.to_dict()
                row_dict["datum"] = None
                try:
                    module_obj = ZHAWModule(**row_dict)
                    processed_modules.append(module_obj)
                    logger.info(f"Row {index + 1}: kept without a date (original 'datum' value failed to parse: {ve}).")
                    continue
                except ValidationError:
                    pass  # some other field also broke on retry - fall through and drop the row

            # Any other validation failure (bad time format, missing name,
            # end-time before start-time, ...) means the row can't be
            # trusted at all, so it's dropped - but the whole import still
            # continues with the remaining rows (see the "all rows failed"
            # check below for the one case where we do give up entirely).
            validation_errors += 1
            if validation_errors <= validation_log_limit:
                logger.warning(f"Row {index + 1} failed validation: {ve}. Skipping row.")
            else:
                # Cap the number of individual warnings logged per import so a
                # file with hundreds of bad rows doesn't flood the log output.
                suppressed_validation_logs += 1
        except Exception:
            # Unlike the ValidationError branch above (an expected, already
            # explained data-quality issue), reaching here means something
            # we didn't anticipate went wrong - logger.exception() captures
            # the full traceback, not just the message, since that's what
            # actually makes an "unexpected" failure diagnosable later.
            validation_errors += 1
            logger.exception(f"Unexpected error parsing row {index + 1}.")

    # Summary logging
    if suppressed_validation_logs:
        logger.warning(f"Suppressed {suppressed_validation_logs} additional row validation warnings.")

    logger.info(f"Successfully loaded {len(processed_modules)} modules. Failed rows: {validation_errors}")
    
    if len(processed_modules) == 0 and len(df) > 0:
        # If all rows failed validation, throw an error to the UI
        raise DataLoaderError(
            "All rows failed data validation. Please check your time formats (HH:MM) and data types.",
            i18n_key="upload.error_all_rows_failed",
        )

    return processed_modules