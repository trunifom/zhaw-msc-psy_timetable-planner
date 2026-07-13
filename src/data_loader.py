"""
ZHAW MSc Psychology - Timetable Planner (Data Integration Layer)
Author: HealthData CodeArchitect
Description: Robust data ingestion, validation, and transformation module.
Focuses on defensive programming to ensure high UI/UX stability by catching
and correcting data anomalies before they reach the presentation layer.
"""

import pandas as pd
import logging
import re
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
    """Base exception for data loading issues. Designed to be caught by the GUI."""
    pass

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

        # Candidate 2: two-line header (common in exports with merged cells).
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

            if (
                required_hits > best_required_hits
                or (required_hits == best_required_hits and total_hits > best_total_hits)
            ):
                best_headers = candidate_headers
                best_start_row = data_start_row
                best_required_hits = required_hits
                best_total_hits = total_hits

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
            raw_dates = df["datum"].astype(str).str.strip()

            # Parse ISO-like timestamps first to avoid day/month swapping.
            iso_mask = raw_dates.str.match(r"^\d{4}-\d{2}-\d{2}(?:[ T].*)?$", na=False)
            parsed_iso = pd.to_datetime(raw_dates.where(iso_mask), errors="coerce")

            # Parse remaining values as day-first (e.g., 15.09.2026).
            parsed_local = pd.to_datetime(raw_dates.where(~iso_mask), errors="coerce", dayfirst=True)

            parsed_dates = parsed_iso.combine_first(parsed_local)
            df["datum"] = parsed_dates.dt.date

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

                # Remove rows that look like duplicated header rows inside the sheet.
                row_header_tokens = {_normalize_label(row.get(col)) for col in required_like}
                if {"modulname", "wochentag", "startzeit", "endzeit"}.issubset(row_header_tokens):
                    keep_mask.append(False)
                    continue

                keep_mask.append(True)

            df = df.loc[keep_mask].reset_index(drop=True)

        return df

    except Exception as e:
        logger.error(f"Sanitization failed: {str(e)}")
        raise DataSanitizationError(f"Failed to clean dataset: {str(e)}")

# ==========================================
# 5. MAIN DATA LOADER LOGIC
# ==========================================
def load_schedule_from_dataframe(raw_df: pd.DataFrame) -> List[ZHAWModule]:
    """
    Main entry point for data ingestion. Takes a raw Pandas DataFrame (uploaded via UI),
    validates its structure, sanitizes the contents, and maps it to strongly-typed 
    Pydantic models (ZHAWModule).

    Args:
        raw_df (pd.DataFrame): The raw dataframe from st.file_uploader.

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
        raise MissingColumnError(error_msg)

    # 5. Data Sanitization (Handle NaNs, cast types securely)
    df = _sanitize_dataframe(df)

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
            # If only the optional date field fails, drop date and retry once.
            errors = ve.errors()
            locations = {err.get("loc", [None])[0] for err in errors if err.get("loc")}
            if locations == {"datum"}:
                row_dict = row.to_dict()
                row_dict["datum"] = None
                try:
                    module_obj = ZHAWModule(**row_dict)
                    processed_modules.append(module_obj)
                    continue
                except ValidationError:
                    pass

            validation_errors += 1
            if validation_errors <= validation_log_limit:
                logger.warning(f"Row {index + 1} failed validation: {ve}. Skipping row.")
            else:
                suppressed_validation_logs += 1
        except Exception as e:
            validation_errors += 1
            logger.error(f"Unexpected error parsing row {index + 1}: {e}")

    # Summary logging
    if suppressed_validation_logs:
        logger.warning(f"Suppressed {suppressed_validation_logs} additional row validation warnings.")

    logger.info(f"Successfully loaded {len(processed_modules)} modules. Failed rows: {validation_errors}")
    
    if len(processed_modules) == 0 and len(df) > 0:
        # If all rows failed validation, throw an error to the UI
        raise DataLoaderError("All rows failed data validation. Please check your time formats (HH:MM) and data types.")

    return processed_modules